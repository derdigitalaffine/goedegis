"""Enqueue due synchronization jobs from registered sources.

The scheduler does not fetch data itself. It snapshots the configured source into a
normal durable job so the existing worker retry/cancel lifecycle remains authoritative.
"""
import json,time
from .store import connect,read_config,add_job


def due_sources(now=None):
    now=time.time() if now is None else now
    cfg=read_config()
    result=[]
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS schedules (
            source_id TEXT PRIMARY KEY,last_run REAL NOT NULL DEFAULT 0,next_run REAL NOT NULL DEFAULT 0)""")
        for source in cfg.get("sources",[]):
            if not source.get("enabled",True): continue
            interval=max(15,int(source.get("interval_minutes",1440)))*60
            row=db.execute("SELECT * FROM schedules WHERE source_id=?",(source["id"],)).fetchone()
            next_run=(row["next_run"] if row else 0)
            if next_run<=now: result.append((source,interval))
    return result


def enqueue_due(now=None):
    now=time.time() if now is None else now
    count=0
    for source,interval in due_sources(now):
        kind=source.get("kind")
        if kind!="wfs":
            # Raster cache jobs need an explicit area and are therefore not globally scheduled.
            continue
        payload={"url":source["url"],"table":"source_"+source["id"].replace("-","")[:24]}
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active=db.execute("SELECT 1 FROM jobs WHERE type='wfs_sync' AND state IN ('queued','running','retry_wait','paused') AND json_extract(payload,'$.source_id')=? LIMIT 1",(source["id"],)).fetchone()
            if not active:
                payload["source_id"]=source["id"]
                add_job("wfs_sync",payload,priority=0,max_attempts=3)
                count+=1
            db.execute("INSERT INTO schedules(source_id,last_run,next_run) VALUES(?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_run=excluded.last_run,next_run=excluded.next_run",(source["id"],now,now+interval))
            db.execute("COMMIT")
    return count


def main():
    while True:
        try: enqueue_due()
        except Exception as exc: print("scheduler:",exc,flush=True)
        time.sleep(30)

if __name__=="__main__": main()
