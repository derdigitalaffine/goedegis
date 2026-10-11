# Goedegis

Self-hosted, modular LAN GIS stack with Docker Compose and MapLibre. **Development integration build, not a fully validated production GIS release.**

## Installation

Prerequisites: Linux, Docker Engine + Compose v2, Python 3.12+ for the terminal menu.

```bash
git clone https://github.com/derdigitalaffine/goedegis.git
cd goedegis
python3 scripts/deploy.py
```

The ncurses menu creates `.env` with random passwords and lets you select service profiles. Start with `core,database,jobs,tiles` for the offline basemap workflow and add `geocoding,routing,ogc,monitoring` as needed. Web UI: `http://<LAN-IP>:8080`. See [deployment notes](docs/DEPLOYMENT.md).

## Architecture

- `core`: Nginx HTTP gateway, bundled MapLibre frontend, FastAPI configuration/job service
- `database`: PostGIS
- `jobs`: SQLite-backed persistent priority queue + worker, WFS sync and streamed OSM PBF downloads
- `tiles`: Tilemaker vector builder + Martin tile server with hot-reloading MBTiles directory
- `geocoding`: Nominatim with Geofabrik import and upstream replication
- `routing`: Valhalla with separate local routing graph
- `ogc`: MapProxy and GeoServer (service/layer publication still requires configuration)
- `monitoring`: Prometheus and cAdvisor

## Offline OSM basemap workflow

1. Enable `core,database,jobs,tiles`.
2. In the web UI, download a `.osm.pbf` extract (the default points to Geofabrik Baden-Württemberg and is configurable).
3. Draw one or more polygon areas.
4. Start **Vektorkarte für Gebiet bauen**. Goedegis passes the area's bounding box to Tilemaker and writes `area-<id>.mbtiles` into persistent `tiles_data`.
5. Martin watches that directory and publishes new/updated MBTiles without a tile-server restart.
6. Choose the generated vector map in the UI and load it in MapLibre. The bundled style deliberately avoids external fonts/sprites so the basic map remains offline-capable.

A single downloaded PBF may cover several Goedegis areas. Each area gets its own MBTiles archive. The current build clips by bounding box, not the exact polygon boundary. Tilemaker's default schema/build settings are used; large extracts can require substantial memory, CPU and disk.

## Confirmed requirements

19 decisions: offline LAN, independent areas, graphical polygon editor, OSM replication, multi-level cache/prewarming, multi-profile routing, WMS/WMTS/WFS, geocoding and POI search, visual map styling, graphical sources/sync, resource dashboard, ncurses deployment, mobile-first responsive HTTP, native GIS endpoints, centralized jobs, modular profiles. No user accounts, no automated backups, no PWA, no extra public REST gateway, no custom geodata upload.

## Implemented versus planned

Implemented: responsive MapLibre UI, polygon areas, OGC source registry/capabilities inspection, bounded raster cache, local OSM PBF download, per-area OSM-to-MBTiles builds, hot-reloading vector tile service, Nominatim/Valhalla/OGC Compose modules, persistent jobs with retries/pause/cancel controls, scheduled WFS sync, resource indicators and ncurses deployment.

Still incomplete: true incremental OSM diff application to the basemap MBTiles, exact polygon clipping, coordinated Nominatim/Valhalla rebuild scheduling, full MapLibre visual style editor, automatic GeoServer publication of synced WFS layers, richer POI autocomplete/filtering and production-scale end-to-end validation.

## Cache and job management

- OGC/XYZ sources have an explicit `cache_allowed` flag. **Check provider licenses and rate limits before enabling it.**
- Raster prewarming is bounded by area and capped at 30,000 tiles per job.
- Jobs persist progress and retry failures with exponential backoff; queued jobs can be paused/resumed and cooperative jobs cancelled.
- WFS sources can be scheduled by their configured `interval_minutes`.
- OSM PBF downloads stream directly to disk instead of buffering the complete extract in worker memory.

## Security

No login is implemented by explicit requirement. **Do not expose port 8080 to the Internet.** Configure LAN firewall rules. HTTP traffic is unencrypted. Database and GIS backend ports are not published directly. Validate data-provider licenses before caching or redistributing sources.
