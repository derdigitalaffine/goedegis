"""Bounded offline raster cache prewarming."""
import os, re
from pathlib import Path
from .geo import geometry,tiles,tile_bounds
from .network import get,validate_url

CACHE=Path(os.getenv("GOEDEGIS_CACHE_DIR","/data/cache"))
SAFE=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")

def run(payload, progress=lambda value,message:None, cancelled=lambda:False):
    source=payload["source"]
    area=payload["area"]
    if not source.get("cache_allowed"):
        raise ValueError("Source has not been approved for caching")
    if not SAFE.fullmatch(source.get("id","")): raise ValueError("Invalid source ID")
    geom,_=geometry(area["geojson"])
    zmin=int(payload.get("zoom_min",area.get("zoom_min",0)))
    zmax=int(payload.get("zoom_max",area.get("zoom_max",12)))
    maximum=int(payload.get("max_tiles",10000))
    if not 1<=maximum<=30000: raise ValueError("max_tiles must be 1..30000")
    selected=list(tiles(geom,zmin,zmax,maximum))
    if not selected: return "No tiles intersect the selected area"
    kind=source.get("kind")
    if kind not in ("wms","wmts","xyz"): raise ValueError("Only WMS/WMTS/XYZ raster sources supported")
    url=source.get("tile_url") or source["url"]
    validate_url(url.replace("{z}","0").replace("{x}","0").replace("{y}","0"))
    if kind in ("xyz","wmts") and not all(token in url for token in ("{z}","{x}","{y}")):
        raise ValueError("XYZ/WMTS source URL must contain {z}, {x}, {y}")
    if kind=="wms" and not source.get("layer"): raise ValueError("WMS layer required")
    done=0
    for z,x,y in selected:
        if cancelled(): raise InterruptedError("Job cancelled")
        folder=CACHE/source["id"]/str(z)/str(x)
        folder.mkdir(parents=True,exist_ok=True)
        target=folder/(str(y)+".png")
        if not target.exists():
            if kind=="wms":
                w,s,e,n=tile_bounds(z,x,y)
                # WMS 1.1.1 with EPSG:3857 avoids WMS 1.3 axis-order ambiguity.
                import math
                radius=6378137
                merc=lambda lon,lat:(radius*math.radians(lon),radius*math.log(math.tan(math.pi/4+math.radians(lat)/2)))
                a,b=merc(w,s);c,d=merc(e,n)
                data,ctype=get(url,{"SERVICE":"WMS","VERSION":"1.1.1","REQUEST":"GetMap",
                    "LAYERS":source["layer"],"STYLES":"","SRS":"EPSG:3857",
                    "BBOX":f"{a},{b},{c},{d}","WIDTH":256,"HEIGHT":256,
                    "FORMAT":"image/png","TRANSPARENT":"TRUE"},max_bytes=4_000_000)
            else:
                data,ctype=get(url.replace("{z}",str(z)).replace("{x}",str(x)).replace("{y}",str(y)),max_bytes=4_000_000)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Upstream did not return PNG tiles")
            temp=target.with_suffix(".partial")
            temp.write_bytes(data)
            temp.replace(target)
        done+=1
        if done%10==0 or done==len(selected):
            progress(round(done*100/len(selected),1),f"{done}/{len(selected)} tiles")
    return f"Cached {len(selected)} tiles"
