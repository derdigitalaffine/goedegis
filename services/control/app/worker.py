import json,os,subprocess,time
from pathlib import Path
from urllib.parse import urlparse,unquote
from .store import connect
from .network import validate_url,download_to
from .cache import run as prewarm
from .vector import vector_id,bbox_text

OSM=Path(os.getenv("GOEDEGIS_OSM_DIR","/data/osm"))
TILES=Path(os.getenv("GOEDEGIS_TILE_DIR","/data/tiles"))

def build_vector_tiles(payload,progress,cancelled):
    if not (OSM/"latest.osm.pbf").is_file():raise ValueError("No OSM PBF available; download one first")
    ident=vector_id(payload["area_id"]);bbox=bbox_text(payload["bbox"])
    requests=TILES/".requests";requests.mkdir(parents=True,exist_ok=True)
    request=requests/(ident+".request");done=requests/(ident+".done");failed=requests/(ident+".failed")
    done.unlink(missing_ok=True);failed.unlink(missing_ok=True);request.write_text(bbox)
    progress(1,"Tilemaker build requested")
    started=time.time();timeout=int(payload.get("timeout_seconds",21600))
    while True:
        if cancelled():
            request.unlink(missing_ok=True)
            raise InterruptedError("Vector build cancellation requested; an already-running Tilemaker process may finish its current build")
        if done.exists():
            done.unlink(missing_ok=True);progress(100,"Vector MBTiles ready");return f"Vector map ready: {ident}.mbtiles"
        if failed.exists():
            reason=failed.read_text(errors="replace")[:300];failed.unlink(missing_ok=True);raise ValueError("Tilemaker failed: "+reason)
        if time.time()-started>timeout:
            request.unlink(missing_ok=True);raise TimeoutError("Vector build timed out")
        elapsed=time.time()-started
        progress(min(95,2+elapsed/60),"Tilemaker is building vector tiles");time.sleep(3)

def run_job(kind,payload,progress=lambda a,b:None,cancelled=lambda:False):
    if kind=="tile_prewarm":return prewarm(payload,progress,cancelled)
    if kind=="download_osm":
        url=validate_url(payload["url"])
        if not urlparse(url).path.lower().endswith(".osm.pbf"):raise ValueError("Only .osm.pbf downloads supported")
        target=OSM/"latest.osm.pbf"
        def dl_progress(current,total):
            value=round(current*100/total,1) if total else 0
            progress(min(99,value),f"Downloaded {current//(1024*1024)} MiB"+(f" / {total//(1024*1024)} MiB" if total else ""))
        size=download_to(url,target,max_bytes=int(payload.get("max_bytes",8_000_000_000)),timeout=1800,progress=dl_progress,cancelled=cancelled)
        return f"OSM extract downloaded ({size//(1024*1024)} MiB)"
    if kind=="build_vector_tiles":return build_vector_tiles(payload,progress,cancelled)
    if kind=="wfs_sync":
        url=validate_url(payload["url"]);table=payload.get("table","wfs_import")
        if not table or not table.replace("_","").isalnum() or not table[0].isalpha():raise ValueError("Invalid table")
        p=urlparse(os.environ["POSTGRES_DSN"])
        dsn="PG:host={host} port={port} dbname={db} user={user} password={password}".format(host=p.hostname,port=p.port or 5432,db=p.path.lstrip("/"),user=unquote(p.username or ""),password=unquote(p.password or ""))
        subprocess.run(["ogr2ogr","-f","PostgreSQL",dsn,"WFS:"+url,"-nln","synced."+table,"-overwrite","-lco","GEOMETRY_NAME=geom"],check=True,timeout=3600)
        return "WFS synchronized"
    raise ValueError("Unknown job type")

def main():
    with connect() as db:db.execute("UPDATE jobs SET state='queued',message='Requeued after worker restart',next_run=?,updated=? WHERE state='running'",(time.time(),time.time()))
    while True:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM jobs WHERE state IN ('queued','retry_wait') AND next_run<=? ORDER BY priority DESC,created ASC LIMIT 1",(time.time(),)).fetchone()
            if row:db.execute("UPDATE jobs SET state='running',attempts=attempts+1,updated=? WHERE id=?",(time.time(),row["id"]))
            db.execute("COMMIT")
        if not row:time.sleep(2);continue
        def cancelled():
            with connect() as db:
                found=db.execute("SELECT cancel_requested FROM jobs WHERE id=?",(row["id"],)).fetchone();return bool(found and found[0])
        def progress(value,message):
            with connect() as db:db.execute("UPDATE jobs SET progress=?,message=?,updated=? WHERE id=?",(value,message,time.time(),row["id"]))
        try:
            message=run_job(row["type"],json.loads(row["payload"]),progress,cancelled);state="cancelled" if cancelled() else "done"
        except InterruptedError as exc:state,message="cancelled",str(exc)
        except Exception as exc:state,message="failed",str(exc)[:500]
        attempts=row["attempts"]+1
        if state=="failed" and attempts<row["max_attempts"]:state="retry_wait";next_run=time.time()+min(3600,30*2**(attempts-1))
        else:next_run=0
        with connect() as db:db.execute("UPDATE jobs SET state=?,message=?,progress=?,next_run=?,updated=? WHERE id=?",(state,message,100 if state=="done" else 0,next_run,time.time(),row["id"]))

if __name__=="__main__":main()
