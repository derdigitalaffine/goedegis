"""Enqueue due synchronization and offline basemap refresh jobs."""
import json,os,time,uuid
from .store import connect,read_config


def ensure_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS schedules (
        source_id TEXT PRIMARY KEY,last_run REAL NOT NULL DEFAULT 0,next_run REAL NOT NULL DEFAULT 0)""")


def _enqueue(db,kind,payload,now,priority=0,max_attempts=3,message="Scheduled job"):
    job_id=str(uuid.uuid4())
    db.execute("""INSERT INTO jobs
        (id,type,payload,state,priority,progress,message,created,updated,max_attempts,next_run)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id,kind,json.dumps(payload),"queued",priority,0,message,now,now,max_attempts,now))
    return job_id


def _active(db,kind,json_path,value):
    return db.execute(
        "SELECT 1 FROM jobs WHERE type=? AND state IN ('queued','running','retry_wait','paused') AND json_extract(payload,?)=? LIMIT 1",
        (kind,json_path,value),
    ).fetchone()


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
            if not _active(db,"wfs_sync","$.source_id",source["id"]):
                payload={"url":source["url"],"table":"source_"+source["id"].replace("-","")[:24],"source_id":source["id"]}
                _enqueue(db,"wfs_sync",payload,now,message="Scheduled source sync");count+=1
            db.execute("INSERT INTO schedules(source_id,last_run,next_run) VALUES(?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_run=excluded.last_run,next_run=excluded.next_run",(source["id"],now,now+interval))
            db.execute("COMMIT")
    count+=enqueue_osm_refresh(cfg,now)
    return count


def enqueue_osm_refresh(cfg=None,now=None,force=False):
    now=time.time() if now is None else now;cfg=read_config() if cfg is None else cfg
    settings=cfg.get("settings",{});hours=max(1,int(settings.get("osm_refresh_hours",24)))
    if not settings.get("osm_auto_refresh",False) and not force:return 0
    pbf_url=settings.get("osm_pbf_url") or os.getenv("OSM_PBF_URL","")
    replication_url=settings.get("osm_replication_url") or os.getenv("OSM_REPLICATION_URL","")
    if not pbf_url:return 0
    with connect() as db:
        ensure_table(db);key="__osm_snapshot__";db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT next_run FROM schedules WHERE source_id=?",(key,)).fetchone()
        if not force and row and row["next_run"]>now:db.execute("COMMIT");return 0
        active=db.execute("SELECT 1 FROM jobs WHERE type IN ('download_osm','update_osm') AND state IN ('queued','running','retry_wait','paused') LIMIT 1").fetchone()
        count=0
        if not active:
            payload={"url":pbf_url,"replication_url":replication_url,"rebuild_vectors":True}
            _enqueue(db,"update_osm",payload,now,priority=20,max_attempts=3,message="Scheduled incremental OSM refresh");count=1
        db.execute("INSERT INTO schedules(source_id,last_run,next_run) VALUES(?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_run=excluded.last_run,next_run=excluded.next_run",(key,now,now+hours*3600))
        db.execute("COMMIT");return count


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
