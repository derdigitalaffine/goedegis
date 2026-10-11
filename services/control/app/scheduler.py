"""Enqueue due WFS synchronization jobs from registered sources."""
import json,time,uuid
from .store import connect,read_config


def ensure_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS schedules (
        source_id TEXT PRIMARY KEY,last_run REAL NOT NULL DEFAULT 0,next_run REAL NOT NULL DEFAULT 0)""")


def enqueue_due(now=None):
    now=time.time() if now is None else now
    cfg=read_config();count=0
    with connect() as db:
        ensure_table(db)
        for source in cfg.get("sources",[]):
            if not source.get("enabled",True) or source.get("kind")!="wfs": continue
            interval=max(15,int(source.get("interval_minutes",1440)))*60
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT next_run FROM schedules WHERE source_id=?",(source["id"],)).fetchone()
            if row and row["next_run"]>now:
                db.execute("COMMIT");continue
            active=db.execute("SELECT 1 FROM jobs WHERE type='wfs_sync' AND state IN ('queued','running','retry_wait','paused') AND json_extract(payload,'$.source_id')=? LIMIT 1",(source["id"],)).fetchone()
            if not active:
                payload={"url":source["url"],"table":"source_"+source["id"].replace("-","")[:24],"source_id":source["id"]}
                job_id=str(uuid.uuid4())
                db.execute("""INSERT INTO jobs
                    (id,type,payload,state,priority,progress,message,created,updated,max_attempts,next_run)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (job_id,"wfs_sync",json.dumps(payload),"queued",0,0,"Scheduled source sync",now,now,3,now))
                count+=1
            db.execute("INSERT INTO schedules(source_id,last_run,next_run) VALUES(?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_run=excluded.last_run,next_run=excluded.next_run",(source["id"],now,now+interval))
            db.execute("COMMIT")
    return count


def status():
    with connect() as db:
        ensure_table(db)
        return [dict(r) for r in db.execute("SELECT * FROM schedules ORDER BY next_run")]


def main():
    while True:
        try: enqueue_due()
        except Exception as exc: print("scheduler:",exc,flush=True)
        time.sleep(30)

if __name__=="__main__": main()
