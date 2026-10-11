import json, os, subprocess, time
from pathlib import Path
from urllib.parse import urlparse,unquote
from .store import connect,read_config
from .network import get,validate_url
from .cache import run as prewarm

OSM=Path(os.getenv("GOEDEGIS_OSM_DIR","/data/osm"))

def run_job(kind,payload,progress=lambda a,b:None,cancelled=lambda:False):
    if kind=="tile_prewarm":
        return prewarm(payload,progress,cancelled)
    if kind=="download_osm":
        url=validate_url(payload["url"])
        if not urlparse(url).path.lower().endswith(".osm.pbf"):
            raise ValueError("Only .osm.pbf downloads supported")
        # Bounded extract download; large imports need explicit storage capacity.
        data,_=get(url,max_bytes=2_000_000_000,timeout=1800)
        if cancelled(): raise InterruptedError("Cancelled")
        OSM.mkdir(parents=True,exist_ok=True)
        target=OSM/"latest.osm.pbf"
        tmp=target.with_suffix(".partial")
        tmp.write_bytes(data)
        tmp.replace(target)
        return "OSM extract downloaded; downstream import still separate"
    if kind=="wfs_sync":
        url=validate_url(payload["url"])
        table=payload.get("table","wfs_import")
        if not table or not table.replace("_","").isalnum() or not table[0].isalpha():
            raise ValueError("Invalid table")
        p=urlparse(os.environ["POSTGRES_DSN"])
        dsn="PG:host={host} port={port} dbname={db} user={user} password={password}".format(
            host=p.hostname,port=p.port or 5432,db=p.path.lstrip("/"),
            user=unquote(p.username or ""),password=unquote(p.password or ""))
        subprocess.run(["ogr2ogr","-f","PostgreSQL",dsn,"WFS:"+url,
                        "-nln","synced."+table,"-overwrite","-lco","GEOMETRY_NAME=geom"],
                        check=True,timeout=3600)
        return "WFS synchronized"
    raise ValueError("Unknown job type")

def main():
    while True:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("""SELECT * FROM jobs WHERE state IN ('queued','retry_wait')
                AND next_run<=? ORDER BY priority DESC,created ASC LIMIT 1""",(time.time(),)).fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running',attempts=attempts+1,updated=? WHERE id=?",
                           (time.time(),row["id"]))
            db.execute("COMMIT")
        if not row:
            time.sleep(2)
            continue
        def cancelled():
            with connect() as db:
                found=db.execute("SELECT cancel_requested FROM jobs WHERE id=?",(row["id"],)).fetchone()
                return bool(found and found[0])
        def progress(value,message):
            with connect() as db:
                db.execute("UPDATE jobs SET progress=?,message=?,updated=? WHERE id=?",
                           (value,message,time.time(),row["id"]))
        try:
            message=run_job(row["type"],json.loads(row["payload"]),progress,cancelled)
            state="cancelled" if cancelled() else "done"
        except InterruptedError as exc:
            state,message="cancelled",str(exc)
        except Exception as exc:
            state,message="failed",str(exc)[:500]
        attempts=row["attempts"]+1
        if state=="failed" and attempts<row["max_attempts"]:
            state="retry_wait"
            next_run=time.time()+min(3600,30*2**(attempts-1))
        else: next_run=0
        with connect() as db:
            db.execute("""UPDATE jobs SET state=?,message=?,progress=?,next_run=?,updated=?
                          WHERE id=?""",
                       (state,message,100 if state=="done" else 0,next_run,time.time(),row["id"]))

if __name__=="__main__":
    main()
