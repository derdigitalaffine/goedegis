# Goedegis

Self-hosted, modular LAN GIS stack with Docker Compose and MapLibre. **Development integration build, not a fully validated production GIS release.**

## Installation

Prerequisites: Linux, Docker Engine + Compose v2, Python 3.12+ for the terminal menu.

```bash
git clone https://github.com/derdigitalaffine/goedegis.git
cd goedegis
python3 scripts/deploy.py
```

The ncurses menu creates `.env` with random passwords and lets you select service profiles. Start with `core,database,jobs` and add `tiles,geocoding,routing,ogc,monitoring` as needed. Web UI: `http://<LAN-IP>:8080`. See [deployment notes](docs/DEPLOYMENT.md).

## Architecture

- `core`: Nginx HTTP gateway, bundled MapLibre frontend, FastAPI configuration/job service
- `database`: PostGIS
- `jobs`: SQLite-backed persistent priority queue + worker, OSM PBF download and WFS import
- `tiles`: TileServer GL; needs separately provisioned local MBTiles and style configuration
- `geocoding`: Nominatim with Geofabrik import and upstream replication
- `routing`: Valhalla with separate local routing graph
- `ogc`: MapProxy and GeoServer (service/layer configuration required)
- `monitoring`: Prometheus and cAdvisor

## Confirmed requirements

19 decisions: offline LAN, independent areas, graphical polygon editor, OSM replication, multi-level cache/prewarming, multi-profile routing, WMS/WMTS/WFS, geocoding and POI search, visual map styling, graphical sources/sync, resource dashboard, ncurses deployment, mobile-first responsive HTTP, native GIS endpoints, centralized jobs, modular profiles. No user accounts, no automated backups, no PWA, no extra public REST gateway, no custom geodata upload.

## Implemented versus planned

The initial implementation includes responsive MapLibre canvas, simple polygon creation/deletion, source registry, Nominatim query, Valhalla route request, job queue and resource indicators, and Compose service definitions. **Not yet complete:** automated per-area replication, full vector map pipeline, fully offline preseeded map coverage, MapProxy layer editor, WFS publication, POI autocomplete, map style editor, robust retry/pause/recovery, automated tile prewarming and production-scale validation. The UI exposes an internal `/control` API for configuration; it is not intended as a general-purpose external GIS gateway.

## Security

No login is implemented by explicit requirement. **Do not expose port 8080 to the Internet.** Configure LAN firewall rules. HTTP traffic is unencrypted. Docker database ports are internal. Validate provider licenses before caching public or official services.
