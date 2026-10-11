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
- `jobs`: SQLite-backed persistent priority queue + worker, WFS sync, streamed OSM PBF downloads and Pyosmium replication updates
- `tiles`: Tilemaker vector builder + Martin tile server with hot-reloading MBTiles directory
- `geocoding`: Nominatim with Geofabrik import and upstream replication
- `routing`: Valhalla with separate local routing graph
- `ogc`: MapProxy and GeoServer (service/layer publication still requires configuration)
- `monitoring`: Prometheus and cAdvisor

## Offline OSM basemap workflow

1. Enable `core,database,jobs,tiles`.
2. In the web UI, configure a `.osm.pbf` extract and matching replication URL. The default points to Geofabrik Baden-Württemberg.
3. Optionally enable automatic refresh and choose the interval. **OSM jetzt aktualisieren** forces a refresh immediately.
4. Goedegis uses `pyosmium-up-to-date` to apply replication diffs to the persistent PBF. If replication cannot be bootstrapped or applied, the worker can fall back to a fresh snapshot download.
5. Draw one or more polygon areas and start **Vektorkarte bauen**. Goedegis passes the area's bounding box to Tilemaker and writes `area-<id>.mbtiles` into persistent `tiles_data`.
6. After a changed PBF is synchronized, vector rebuild jobs are automatically queued for configured areas. Martin watches the directory and publishes updated MBTiles without a tile-server restart.
7. Choose the generated vector map in the UI and load it in MapLibre. The bundled style deliberately avoids external fonts/sprites so the basic map remains offline-capable.

A single downloaded PBF may cover several Goedegis areas. Each area gets its own MBTiles archive. The current build clips by bounding box, not the exact polygon boundary. Goedegis uses its own OSM-only Tilemaker layer configuration with Tilemaker's bundled OpenMapTiles processing script; large extracts can require substantial memory, CPU and disk.

## Official German geodata presets

The source manager contains curated one-click presets for official services from the Bundesamt für Kartographie und Geodäsie (BKG):

- TopPlusOpen WMS (`web`)
- TopPlusOpen WMTS (`web`, Web Mercator tile template)
- Verwaltungsgebiete VG250 WMS (`vg250_lan`)
- Verwaltungsgebiete VG250 WFS (`vg250_gem`)

Preset sources retain provider, attribution and licence metadata. MapLibre receives linked BKG/licence/data-source attribution when a locally cached TopPlusOpen raster source is displayed. TopPlusOpen WMS/WMTS presets enable caching because the BKG documentation explicitly describes offline storage under a required source notice. **For offline publication/export, the BKG also requires a date-specific TopPlusOpen data-sources reference. Goedegis does not yet generate that date-specific PDF reference automatically; the operator must add the required offline source notice.** VG250 presets remain conservative with caching disabled by default; enable caching only after checking the terms for the intended use.

The WMTS preset stores the standards service URL separately from the tile-template URL. This keeps GetCapabilities discovery intact while the offline cache can request `{z}/{y}/{x}` tiles directly.

## Confirmed requirements

19 decisions: offline LAN, independent areas, graphical polygon editor, OSM replication, multi-level cache/prewarming, multi-profile routing, WMS/WMTS/WFS, geocoding and POI search, visual map styling, graphical sources/sync, resource dashboard, ncurses deployment, mobile-first responsive HTTP, native GIS endpoints, centralized jobs, modular profiles. No user accounts, no automated backups, no PWA, no extra public REST gateway, no custom geodata upload.

## Implemented versus planned

Implemented: responsive MapLibre UI with Playwright desktop/mobile checks, polygon areas, OGC source registry/capabilities inspection, curated official BKG presets with attribution metadata, bounded raster cache, streamed OSM PBF download, incremental PBF replication with Pyosmium, automatic/manual refresh controls, per-area OSM-to-MBTiles rebuilds, hot-reloading vector tile service, Nominatim/Valhalla/OGC Compose modules, persistent jobs with retries/pause/cancel controls, scheduled WFS sync, resource indicators and ncurses deployment.

Still incomplete: incremental mutation of existing MBTiles (the synchronized PBF is incremental but affected area MBTiles are rebuilt), exact polygon clipping, automatic date-specific TopPlusOpen offline source-note generation, coordinated Nominatim/Valhalla rebuild scheduling, full MapLibre visual style editor, automatic GeoServer publication of synced WFS layers, richer POI autocomplete/filtering and production-scale end-to-end validation.

## Cache and job management

- OGC/XYZ sources have an explicit `cache_allowed` flag. **Check provider licenses and rate limits before enabling it.**
- Raster prewarming is bounded by area and capped at 30,000 tiles per job.
- Jobs persist progress and retry failures with exponential backoff; queued jobs can be paused/resumed and cooperative jobs cancelled.
- WFS sources can be scheduled by their configured `interval_minutes`.
- OSM PBF downloads stream directly to disk instead of buffering the complete extract in worker memory.
- OSM replication updates are batched, cancellable, and only enqueue vector rebuilds when the PBF actually changed.

## Security

No login is implemented by explicit requirement. **Do not expose port 8080 to the Internet.** Configure LAN firewall rules. HTTP traffic is unencrypted. Database and GIS backend ports are not published directly. Validate data-provider licenses before caching or redistributing sources.
