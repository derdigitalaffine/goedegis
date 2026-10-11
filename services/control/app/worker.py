import json, os, subprocess, time
from pathlib import Path
from urllib.parse import urlparse, unquote
import httpx
from .store import connect

CACHE = Path(os.getenv("GOEDEGIS_CACHE_DIR", "/data/cache"))
OSM = Path(os.getenv("GOEDEGIS_OSM_DIR", "/data/osm"))

def validate_url(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("Only HTTP(S) URLs are supported")
    import ipaddress, socket
    addresses = socket.getaddrinfo(p.hostname, None)
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private/reserved addresses blocked for worker downloads")
    return url

def run_job(kind, payload):
    if kind == "download_osm":
        url = validate_url(payload["url"])
        if not url.lower().endswith(".osm.pbf"):
            raise ValueError("Only .osm.pbf downloads supported")
        OSM.mkdir(parents=True, exist_ok=True)
        target = OSM / "latest.osm.pbf"
        temp = target.with_suffix(".partial")
        with httpx.stream("GET", url, timeout=1800, follow_redirects=False) as response:
            response.raise_for_status()
            with temp.open("wb") as out:
                for chunk in response.iter_bytes():
                    out.write(chunk)
        temp.replace(target)
        return "OSM extract downloaded; separate import pipeline still required"
    if kind == "wfs_sync":
        url = validate_url(payload["url"])
        table = payload.get("table", "wfs_import")
        if not table or not table.replace("_", "").isalnum() or not table[0].isalpha():
            raise ValueError("Invalid table")
        p = urlparse(os.environ["POSTGRES_DSN"])
        if p.scheme not in ("postgresql", "postgres"):
            raise ValueError("Invalid database URL")
        dsn = "PG:host={host} port={port} dbname={db} user={user} password={password}".format(
            host=p.hostname, port=p.port or 5432, db=p.path.lstrip("/"),
            user=unquote(p.username or ""), password=unquote(p.password or ""))
        subprocess.run(["ogr2ogr", "-f", "PostgreSQL", dsn,
            "WFS:" + url, "-nln", "synced." + table, "-overwrite", "-lco", "GEOMETRY_NAME=geom"],
            check=True, timeout=3600)
        return "WFS synced"
    if kind == "tile_prewarm":
        raise ValueError("Tile prewarming requires a permitted source and seeding plan")
    raise ValueError("Unknown job type")

def main():
    while True:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY priority DESC, created ASC LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running', updated=? WHERE id=?", (time.time(), row["id"]))
            db.execute("COMMIT")
        if not row:
            time.sleep(2)
            continue
        try:
            message = run_job(row["type"], json.loads(row["payload"]))
            state = "done"
        except Exception as exc:
            state, message = "failed", str(exc)[:1000]
        with connect() as db:
            db.execute("UPDATE jobs SET state=?, message=?, progress=?, updated=? WHERE id=?",
                       (state, message, 100 if state == "done" else 0, time.time(), row["id"]))

if __name__ == "__main__":
    main()
