import json,os,subprocess,time
from pathlib import Path
from urllib.parse import urlparse,unquote
from .store import connect,read_config,add_job
from .network import validate_url,download_to
from .cache import run as prewarm
from .vector import vector_id,bbox_text
from .geo import geometry

OSM=Path(os.getenv("GOEDEGIS_OSM_DIR","/data/osm"))
TILES=Path(os.getenv("GOEDEGIS_TILE_DIR","/data/tiles"))

def prepare_area_extract(payload,progress,cancelled):
    source=OSM/"latest.osm.pbf"
    if not source.is_file():raise ValueError("No OSM PBF available; download one first")
    ident=vector_id(payload["area_id"]);geom,_=geometry(payload["geojson"])
    area_dir=OSM/"areas";area_dir.mkdir(parents=True,exist_ok=True)
    polygon=area_dir/(ident+".geojson");extract=area_dir/(ident+".osm.pbf");log=area_dir/(ident+".extract.log")
    extract.unlink(missing_ok=True)
    polygon.write_text(json.dumps({"type":"Feature","properties":{},"geometry":geom},separators=(",",":")))
    progress(2,"Clipping OSM data to area polygon")
    command=["osmium","extract","--polygon",str(polygon),"--strategy","complete_ways","--set-bounds","--output",str(extract),"--overwrite",str(source)]
    try:
        code=_run_cancellable(command,log,int(payload.get("extract_timeout_seconds",3600)),cancelled,label="OSM area extraction")
        if code!=0:
            detail=log.read_text(errors="replace")[-500:] if log.exists() else "osmium extract failed"
            raise RuntimeError(detail)
        subprocess.run(["osmium","fileinfo","--check",str(extract)],check=True,timeout=300)
        if not extract.is_file() or extract.stat().st_size==0:raise ValueError("OSM area extract is empty")
        progress(15,"Area PBF ready; starting Tilemaker")
        return extract,polygon,log
    except Exception:
        extract.unlink(missing_ok=True);polygon.unlink(missing_ok=True)
        raise

def build_vector_tiles(payload,progress,cancelled):
    ident=vector_id(payload["area_id"]);bbox=bbox_text(payload["bbox"])
    extract,polygon,extract_log=prepare_area_extract(payload,progress,cancelled)
    requests=TILES/".requests";requests.mkdir(parents=True,exist_ok=True)
    request=requests/(ident+".request");done=requests/(ident+".done");failed=requests/(ident+".failed")
    try:
        done.unlink(missing_ok=True);failed.unlink(missing_ok=True);request.write_text(bbox+"\narea\n")
        progress(16,"Tilemaker build requested for polygon extract");started=time.time();timeout=int(payload.get("timeout_seconds",21600))
        while True:
            if cancelled():request.unlink(missing_ok=True);raise InterruptedError("Vector build cancellation requested; an already-running Tilemaker process may finish its current build")
            if done.exists():done.unlink(missing_ok=True);progress(100,"Polygon-clipped vector MBTiles ready");return f"Vector map ready: {ident}.mbtiles"
            if failed.exists():
                reason=failed.read_text(errors="replace")[:300];failed.unlink(missing_ok=True);raise ValueError("Tilemaker failed: "+reason)
            if time.time()-started>timeout:request.unlink(missing_ok=True);raise TimeoutError("Vector build timed out")
            progress(min(95,17+(time.time()-started)/60),"Tilemaker is building polygon-clipped vector tiles");time.sleep(3)
    finally:
        extract.unlink(missing_ok=True);polygon.unlink(missing_ok=True);extract_log.unlink(missing_ok=True)

def enqueue_vector_rebuilds():
    queued=0
    for area in read_config().get("areas",[]):
        try:geom,bbox=geometry(area["geojson"])
        except (KeyError,ValueError):continue
        with connect() as db:active=db.execute("SELECT 1 FROM jobs WHERE type='build_vector_tiles' AND state IN ('queued','running','retry_wait','paused') AND json_extract(payload,'$.area_id')=? LIMIT 1",(area["id"],)).fetchone()
        if active:continue
        add_job("build_vector_tiles",{"area_id":area["id"],"bbox":bbox,"geojson":geom,"timeout_seconds":21600},priority=10,max_attempts=2);queued+=1
    return queued

def download_osm(payload,progress,cancelled):
    url=validate_url(payload["url"])
    if not urlparse(url).path.lower().endswith(".osm.pbf"):raise ValueError("Only .osm.pbf downloads supported")
    target=OSM/"latest.osm.pbf"
    def dl_progress(current,total):
        value=round(current*100/total,1) if total else 0;progress(min(99,value),f"Downloaded {current//(1024*1024)} MiB"+(f" / {total//(1024*1024)} MiB" if total else ""))
    size=download_to(url,target,max_bytes=int(payload.get("max_bytes",8_000_000_000)),timeout=1800,progress=dl_progress,cancelled=cancelled)
    rebuilds=enqueue_vector_rebuilds() if payload.get("rebuild_vectors") else 0
    return f"OSM extract downloaded ({size//(1024*1024)} MiB); queued {rebuilds} vector rebuild(s)"

def _run_cancellable(cmd,log_path,timeout,cancelled,label="OSM replication update"):
    started=time.time();log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open("w") as log:
        proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,text=True)
        while proc.poll() is None:
            if cancelled():
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
                raise InterruptedError(label+" cancelled")
            if time.time()-started>timeout:
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
                raise TimeoutError(label+" timed out")
            time.sleep(1)
        return proc.returncode

def update_osm(payload,progress,cancelled):
    current=OSM/"latest.osm.pbf";replication=payload.get("replication_url")
    if not current.is_file() or not replication:
        progress(1,"No usable replication state; downloading a fresh snapshot")
        return download_osm(payload,progress,cancelled)
    replication=validate_url(replication);work=OSM/"replication";work.mkdir(parents=True,exist_ok=True)
    before=(current.stat().st_size,current.stat().st_mtime_ns);size_mb=max(16,min(1024,int(payload.get("replication_batch_mb",256))));timeout=int(payload.get("replication_timeout_seconds",3600));max_batches=max(1,min(20,int(payload.get("replication_max_batches",8))));log=work/"pyosmium-up-to-date.log"
    for batch in range(max_batches):
        if cancelled():raise InterruptedError("OSM replication update cancelled")
        progress(min(75,5+batch*8),f"Applying OSM replication batch {batch+1}")
        base=["pyosmium-up-to-date","--server",replication,"--size",str(size_mb),"--tmpdir",str(work),str(current)]
        code=_run_cancellable(base,log,timeout,cancelled)
        if code>1 and batch==0:
            progress(8,"Bootstrapping OSM replication state")
            bootstrap=["pyosmium-up-to-date","--ignore-osmosis-headers","--server",replication,"--size",str(size_mb),"--tmpdir",str(work),str(current)]
            code=_run_cancellable(bootstrap,log,timeout,cancelled)
        if code==0:break
        if code==1:continue
        detail=log.read_text(errors="replace")[-500:] if log.exists() else "pyosmium-up-to-date failed"
        if payload.get("fallback_snapshot",True):
            progress(1,"Replication failed; downloading a fresh snapshot")
            return download_osm(payload,progress,cancelled)
        raise RuntimeError(detail)
    else:raise RuntimeError("OSM replication is still behind after the configured batch limit")
    after=(current.stat().st_size,current.stat().st_mtime_ns)
    if after==before:return "OSM data already current"
    progress(80,"OSM snapshot updated")
    rebuilds=enqueue_vector_rebuilds() if payload.get("rebuild_vectors") else 0
    return f"OSM replication applied; queued {rebuilds} vector rebuild(s)"

def run_job(kind,payload,progress=lambda a,b:None,cancelled=lambda:False):
    if kind=="tile_prewarm":return prewarm(payload,progress,cancelled)
    if kind=="download_osm":return download_osm(payload,progress,cancelled)
    if kind=="update_osm":return update_osm(payload,progress,cancelled)
    if kind=="build_vector_tiles":return build_vector_tiles(payload,progress,cancelled)
    if kind=="wfs_sync":
        url=validate_url(payload["url"]);table=payload.get("table","wfs_import");layer=payload.get("layer","")
        if not table or not table.replace("_","").isalnum() or not table[0].isalpha():raise ValueError("Invalid table")
        if layer and not all(c.isalnum() or c in "_.:-" for c in layer):raise ValueError("Invalid WFS layer")
        p=urlparse(os.environ["POSTGRES_DSN"]);dsn="PG:host={host} port={port} dbname={db} user={user} password={password}".format(host=p.hostname,port=p.port or 5432,db=p.path.lstrip("/"),user=unquote(p.username or ""),password=unquote(p.password or ""))
        command=["ogr2ogr","-f","PostgreSQL",dsn,"WFS:"+url]
        if layer:command.append(layer)
        command.extend(["-nln","synced."+table,"-overwrite","-lco","GEOMETRY_NAME=geom"])
        subprocess.run(command,check=True,timeout=3600);return "WFS synchronized"
    raise ValueError("Unknown job type")

def main():
    with connect() as db:db.execute("UPDATE jobs SET state='queued',message='Requeued after worker restart',next_run=?,updated=? WHERE state='running'",(time.time(),time.time()))
    while True:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE");row=db.execute("SELECT * FROM jobs WHERE state IN ('queued','retry_wait') AND next_run<=? ORDER BY priority DESC,created ASC LIMIT 1",(time.time(),)).fetchone()
            if row:db.execute("UPDATE jobs SET state='running',attempts=attempts+1,updated=? WHERE id=?",(time.time(),row["id"]));db.execute("COMMIT")
        if not row:time.sleep(2);continue
        def cancelled():
            with connect() as db:
                found=db.execute("SELECT cancel_requested FROM jobs WHERE id=?",(row["id"],)).fetchone();return bool(found and found[0])
        def progress(value,message):
            with connect() as db:db.execute("UPDATE jobs SET progress=?,message=?,updated=? WHERE id=?",(value,message,time.time(),row["id"]))
        try:message=run_job(row["type"],json.loads(row["payload"]),progress,cancelled);state="cancelled" if cancelled() else "done"
        except InterruptedError as exc:state,message="cancelled",str(exc)
        except Exception as exc:state,message="failed",str(exc)[:500]
        attempts=row["attempts"]+1
        if state=="failed" and attempts<row["max_attempts"]:state="retry_wait";next_run=time.time()+min(3600,30*2**(attempts-1))
        else:next_run=0
        with connect() as db:db.execute("UPDATE jobs SET state=?,message=?,progress=?,next_run=?,updated=? WHERE id=?",(state,message,100 if state=="done" else 0,next_run,time.time(),row["id"]))

if __name__=="__main__":main()
