# Deployment and operational notes

## Start

Requires Linux, Docker Engine, Docker Compose v2, and sufficient storage. For Germany-scale OSM imports, substantial RAM and disk are required.

```bash
python3 scripts/deploy.py
```

The ncurses menu creates a local `.env` with random passwords. Start with `core` and `database`. Enable other profiles as needed. Visit `http://<server-ip>:8080`.

## Data

- The tile server requires locally provisioned MBTiles in its persistent `tiles_data` volume; a blank install has no basemap.
- Nominatim downloads the configured Geofabrik extract on first initialization and requires network access then. Subsequent queries work offline. Updates depend on the configured upstream and the container image.
- Valhalla imports its own routing graph from the configured PBF; initial import requires internet. It does not automatically share Nominatim's database.
- MapProxy requires a permitted upstream. The example points to the local tile service; do not mass-cache third-party public tile endpoints without permission.
- GeoServer's OGC workspace/layer publishing must be configured separately.
- WFS sync jobs use GDAL ogr2ogr; verify the source URL and schema. Do not point them at untrusted services.

## Security

No authentication was requested. Keep port 8080 behind a trusted LAN firewall. Docker's published binding defaults to all interfaces; change `GOEDEGIS_BIND_IP` to a specific LAN address where appropriate. GeoServer and the internal DB have no public host ports.

## Limitations

This is an integration foundation, not an end-to-end validated production release. Visual style editor, autonomous per-area sync orchestration, reliable prewarming, full POI autocomplete, OGC layer publication, automatic routing rebuilds, and full monitoring remain to be built. Do not interpret successful Compose validation as proof of operational data imports.
