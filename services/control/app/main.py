import os, shutil, socket, time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .store import read_config, write_config, add_job, jobs, connect

app = FastAPI(title="Goedegis control plane", docs_url="/control/docs", openapi_url="/control/openapi.json")

class Area(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    geojson: dict
    zoom_min: int = Field(default=0, ge=0, le=22)
    zoom_max: int = Field(default=14, ge=0, le=22)
    layers: list[str] = Field(default_factory=list)
    osm_tags: list[str] = Field(default_factory=list)

class Source(BaseModel):
    name: str
    url: str
    kind: str = Field(pattern="^(wms|wmts|wfs|osm)$")
    enabled: bool = True
    interval_minutes: int = Field(default=1440, ge=15)
    layer: str = ""

class JobRequest(BaseModel):
    type: str = Field(pattern="^(wfs_sync|tile_prewarm|download_osm)$")
    payload: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=-100, le=100)

@app.get("/control/health")
def health():
    return {"ok": True, "service": "goedegis-control"}

@app.get("/control/config")
def get_config():
    return read_config()

@app.put("/control/config")
def set_config(data: dict):
    # LAN only: intentionally no authentication, as requested.
    if not isinstance(data.get("areas", []), list) or not isinstance(data.get("sources", []), list):
        raise HTTPException(422, "Invalid config")
    write_config(data)
    return read_config()

@app.post("/control/areas")
def create_area(area: Area):
    if area.zoom_min > area.zoom_max:
        raise HTTPException(422, "zoom_min must be <= zoom_max")
    if area.geojson.get("type") not in ("Polygon", "MultiPolygon", "Feature"):
        raise HTTPException(422, "Polygon or MultiPolygon required")
    data = read_config()
    entry = {"id": str(__import__("uuid").uuid4()), **area.model_dump()}
    data["areas"].append(entry)
    write_config(data)
    return entry

@app.delete("/control/areas/{area_id}")
def delete_area(area_id: str):
    data = read_config()
    data["areas"] = [a for a in data["areas"] if a["id"] != area_id]
    write_config(data)
    return {"ok": True}

@app.post("/control/sources")
def create_source(source: Source):
    from urllib.parse import urlparse
    parsed = urlparse(source.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(422, "HTTP(S) sources only")
    data = read_config()
    entry = {"id": str(__import__("uuid").uuid4()), **source.model_dump()}
    data["sources"].append(entry)
    write_config(data)
    return entry

@app.delete("/control/sources/{source_id}")
def delete_source(source_id: str):
    data = read_config()
    data["sources"] = [s for s in data["sources"] if s["id"] != source_id]
    write_config(data)
    return {"ok": True}

@app.get("/control/jobs")
def list_jobs():
    return jobs()

@app.post("/control/jobs")
def enqueue(req: JobRequest):
    return {"id": add_job(req.type, req.payload, req.priority)}

@app.post("/control/jobs/{job_id}/cancel")
def cancel(job_id: str):
    with connect() as db:
        row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row: raise HTTPException(404, "Job not found")
        if row["state"] != "queued": raise HTTPException(409, "Only queued jobs can be cancelled safely")
        db.execute("UPDATE jobs SET state='cancelled', updated=? WHERE id=?", (time.time(), job_id))
    return {"ok": True}

@app.get("/control/resources")
def resources():
    import psutil
    cache = Path(os.getenv("GOEDEGIS_CACHE_DIR", "/data/cache"))
    disk = shutil.disk_usage(cache)
    return {"cpu_percent": psutil.cpu_percent(interval=.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total": disk.total, "disk_used": disk.used, "disk_free": disk.free,
            "jobs": len(jobs())}
