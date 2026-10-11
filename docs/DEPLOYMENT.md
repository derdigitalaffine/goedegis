# Deployment and operational notes

## Start

Requires Linux, Docker Engine, Docker Compose v2, and sufficient storage. Large OSM extracts can require substantial RAM, CPU and disk.

```bash
python3 scripts/deploy.py
```

The ncurses menu creates a local `.env` with random passwords. For the complete local basemap path enable `core,database,jobs,tiles`. Visit `http://<server-ip>:8080`.

## Offline OSM basemap

The `jobs` worker streams the configured `.osm.pbf` into the persistent `osm_data` volume. The `tiles` profile starts two separate services:

- **Tilemaker builder** watches build request files and turns the downloaded PBF into one MBTiles archive per Goedegis area.
- **Martin 1.16.1** watches the persistent `tiles_data` directory and publishes newly created or replaced `.mbtiles` archives without needing a tile-server restart.

The build currently uses Tilemaker's default configuration and the selected area's bounding box. It does not clip precisely to arbitrary polygon edges. A PBF must cover the selected area; Goedegis does not automatically verify geographic coverage yet.

For an existing installation, a typical flow is:

```bash
docker compose --profile core --profile database --profile jobs --profile tiles up -d --build
```

Then use the web UI to download an OSM PBF, create/select an area and enqueue its vector-map build. Build progress from Tilemaker itself is not machine-readable in this integration, so the displayed percentage while tiling is an activity indicator rather than an exact completion percentage.

## Other data services

- Nominatim downloads the configured Geofabrik extract on first initialization and requires network access then. Subsequent queries work offline. Updates depend on its configured replication URL.
- Valhalla builds its own routing graph from the configured PBF. It is independent of the Goedegis MBTiles build and of Nominatim.
- MapProxy requires a permitted upstream. Do not bulk-cache third-party public tile endpoints without explicit provider permission.
- GeoServer workspace/layer publication is not yet automated.
- WFS sync jobs use GDAL `ogr2ogr`; enabled WFS sources can be scheduled through their `interval_minutes` setting.

## Persistence

Docker volumes contain the important runtime state:

- `osm_data`: downloaded OSM PBF
- `tiles_data`: generated area MBTiles and builder request/status markers
- `cache_data`: raster prewarming cache
- `jobs_data`: job queue and scheduler state
- `config_data`: areas/source configuration
- service-specific PostGIS, Nominatim, Valhalla, MapProxy, GeoServer and Prometheus volumes

Automatic backups are intentionally not implemented. Stop or quiesce relevant services before manually backing up Docker volumes.

## Security

No authentication was requested. Keep port 8080 behind a trusted LAN firewall. Docker's published binding defaults to all interfaces; change `GOEDEGIS_BIND_IP` to a specific LAN address where appropriate. GeoServer, Martin, Nominatim, Valhalla and PostgreSQL are not published directly as host ports.

## Limitations

The OSM basemap pipeline now creates local vector MBTiles, but true incremental OSM diff application to existing MBTiles is not implemented; a refreshed PBF currently requires a rebuild. Exact polygon clipping, coordinated Nominatim/Valhalla refreshes, full POI controls, automatic GeoServer publishing, a complete style editor and production-scale end-to-end validation remain open work.
