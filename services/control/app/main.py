import os,shutil,uuid
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from .store import read_config,write_config,add_job,jobs,change_job
from .geo import geometry
from .network import validate_url
from .cache import CACHE
from .ogc import capabilities
from .scheduler import status as schedule_status,enqueue_due,enqueue_osm_refresh,reset_osm_schedule

TILES=Path(os.getenv("GOEDEGIS_TILE_DIR","/data/tiles"))
app=FastAPI(title="Goedegis internal control plane",docs_url="/control/docs",openapi_url="/control/openapi.json")

class Area(BaseModel):
    name:str=Field(min_length=1,max_length=100);geojson:dict
    zoom_min:int=Field(default=0,ge=0,le=18);zoom_max:int=Field(default=14,ge=0,le=18)
    layers:list[str]=Field(default_factory=list);osm_tags:list[str]=Field(default_factory=list)
class Source(BaseModel):
    name:str=Field(min_length=1,max_length=100);url:str
    kind:str=Field(pattern="^(wms|wmts|wfs|osm|xyz)$");enabled:bool=True;cache_allowed:bool=False
    interval_minutes:int=Field(default=1440,ge=15);layer:str=""
class JobRequest(BaseModel):
    type:str=Field(pattern="^(wfs_sync|tile_prewarm|download_osm|update_osm|build_vector_tiles)$");payload:dict=Field(default_factory=dict)
    priority:int=Field(default=0,ge=-100,le=100);max_attempts:int=Field(default=3,ge=1,le=10)
class OSMSettings(BaseModel):
    osm_auto_refresh:bool=False
    osm_refresh_hours:int=Field(default=24,ge=1,le=720)
    osm_pbf_url:str=Field(min_length=1,max_length=1000)
    osm_replication_url:str=Field(default="",max_length=1000)

def vector_id(area_id):
    clean="".join(c for c in area_id.lower() if c.isalnum() or c in "-_")
    if not clean or len(clean)>80:raise ValueError("Invalid area ID")
    return "area-"+clean

def vector_payload(area_id):
    cfg=read_config();area=next((a for a in cfg["areas"] if a["id"]==area_id),None)
    if area is None:raise HTTPException(404,"Area not found")
    try:_,bbox=geometry(area["geojson"])
    except ValueError as exc:raise HTTPException(422,str(exc))
    return {"area_id":area_id,"bbox":bbox,"timeout_seconds":21600}

def effective_osm_settings():
    settings=read_config().get("settings",{})
    return {"osm_auto_refresh":bool(settings.get("osm_auto_refresh",False)),"osm_refresh_hours":int(settings.get("osm_refresh_hours",24)),"osm_pbf_url":settings.get("osm_pbf_url") or os.getenv("OSM_PBF_URL",""),"osm_replication_url":settings.get("osm_replication_url") or os.getenv("OSM_REPLICATION_URL","")}

@app.get("/control/health")
def health():return {"ok":True,"service":"goedegis-control"}
@app.get("/control/config")
def get_config():return read_config()
@app.get("/control/settings/osm")
def get_osm_settings():return effective_osm_settings()
@app.put("/control/settings/osm")
def put_osm_settings(settings:OSMSettings):
    try:
        pbf=validate_url(settings.osm_pbf_url)
        if not urlparse(pbf).path.lower().endswith(".osm.pbf"):raise ValueError("OSM PBF URL must end in .osm.pbf")
        replication=validate_url(settings.osm_replication_url) if settings.osm_replication_url else ""
    except ValueError as exc:raise HTTPException(422,str(exc))
    data=read_config();data.setdefault("settings",{}).update({**settings.model_dump(),"osm_pbf_url":pbf,"osm_replication_url":replication});write_config(data);reset_osm_schedule();return effective_osm_settings()
@app.post("/control/osm/refresh")
def refresh_osm():
    if not effective_osm_settings()["osm_pbf_url"]:raise HTTPException(422,"OSM PBF URL is not configured")
    queued=enqueue_osm_refresh(force=True)
    if not queued:raise HTTPException(409,"An OSM refresh is already queued or running")
    return {"queued":queued}
@app.post("/control/areas")
def create_area(area:Area):
    if area.zoom_min>area.zoom_max:raise HTTPException(422,"Invalid zoom range")
    try:geometry(area.geojson)
    except ValueError as exc:raise HTTPException(422,str(exc))
    data=read_config();entry={"id":str(uuid.uuid4()),**area.model_dump()};data["areas"].append(entry);write_config(data);return entry
@app.delete("/control/areas/{area_id}")
def delete_area(area_id:str):
    data=read_config();data["areas"]=[a for a in data["areas"] if a["id"]!=area_id];write_config(data);return {"ok":True}
@app.post("/control/areas/{area_id}/vector-build")
def build_area_vector_map(area_id:str):return {"id":add_job("build_vector_tiles",vector_payload(area_id),priority=10,max_attempts=2)}
@app.get("/control/vector-maps")
def vector_maps():
    TILES.mkdir(parents=True,exist_ok=True);result=[]
    for path in sorted(TILES.glob("area-*.mbtiles")):
        stat=path.stat();result.append({"id":path.stem,"size":stat.st_size,"modified":stat.st_mtime})
    return result
@app.post("/control/sources")
def create_source(source:Source):
    try:validate_url(source.url.replace("{z}","0").replace("{x}","0").replace("{y}","0"))
    except ValueError as exc:raise HTTPException(422,str(exc))
    data=read_config();entry={"id":str(uuid.uuid4()),**source.model_dump()};data["sources"].append(entry);write_config(data);return entry
@app.delete("/control/sources/{source_id}")
def delete_source(source_id:str):
    data=read_config();data["sources"]=[s for s in data["sources"] if s["id"]!=source_id];write_config(data);return {"ok":True}
@app.get("/control/jobs")
def list_jobs():return jobs()
@app.post("/control/jobs")
def enqueue(req:JobRequest):
    payload=req.payload
    if req.type=="tile_prewarm":
        cfg=read_config();area=next((a for a in cfg["areas"] if a["id"]==payload.get("area_id")),None);source=next((s for s in cfg["sources"] if s["id"]==payload.get("source_id")),None)
        if not area or not source:raise HTTPException(404,"Area or source not found")
        if not source.get("cache_allowed"):raise HTTPException(422,"Caching not approved")
        if source["kind"] not in ("wms","wmts","xyz"):raise HTTPException(422,"Raster source required")
        payload={"area":area,"source":source,"zoom_min":area["zoom_min"],"zoom_max":area["zoom_max"],"max_tiles":min(30000,int(payload.get("max_tiles",10000)))}
    elif req.type=="build_vector_tiles":payload=vector_payload(payload.get("area_id",""))
    elif req.type in ("wfs_sync","download_osm","update_osm"):
        try:
            validate_url(payload["url"])
            if req.type=="update_osm" and payload.get("replication_url"):validate_url(payload["replication_url"])
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc))
    return {"id":add_job(req.type,payload,req.priority,req.max_attempts)}
@app.post("/control/jobs/{job_id}/{action}")
def action_job(job_id:str,action:str):
    try:return change_job(job_id,action)
    except KeyError:raise HTTPException(404,"Job not found")
    except ValueError as exc:raise HTTPException(409,str(exc))
@app.get("/control/cache/{source_id}/{z}/{x}/{y}.png")
def cached_tile(source_id:str,z:int,x:int,y:int):
    if not source_id.isascii() or not source_id.replace("_","").replace("-","").isalnum():raise HTTPException(400,"Invalid source ID")
    if not (0<=z<=18 and 0<=x<2**z and 0<=y<2**z):raise HTTPException(400,"Invalid tile coordinates")
    path=CACHE/source_id/str(z)/str(x)/(str(y)+".png")
    if not path.is_file():raise HTTPException(404,"Tile not cached")
    return FileResponse(path,media_type="image/png",headers={"Cache-Control":"public,max-age=86400"})
@app.get("/control/resources")
def resources():
    import psutil
    cache=Path(os.getenv("GOEDEGIS_CACHE_DIR","/data/cache"));cache.mkdir(parents=True,exist_ok=True);disk=shutil.disk_usage(cache)
    return {"cpu_percent":psutil.cpu_percent(interval=.1),"memory_percent":psutil.virtual_memory().percent,"disk_total":disk.total,"disk_used":disk.used,"disk_free":disk.free,"jobs":len(jobs())}
@app.get("/control/sources/{source_id}/capabilities")
def source_capabilities(source_id:str):
    cfg=read_config();source=next((s for s in cfg["sources"] if s["id"]==source_id),None)
    if source is None:raise HTTPException(404,"Source not found")
    if source["kind"] not in ("wms","wmts","wfs"):raise HTTPException(422,"OGC source required")
    try:return capabilities(source["url"],source["kind"])
    except Exception as exc:raise HTTPException(502,"OGC capabilities unavailable: "+str(exc)[:160])
@app.get("/control/schedules")
def schedules():return schedule_status()
@app.post("/control/schedules/run-due")
def run_due():return {"queued":enqueue_due()}
