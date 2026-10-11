"""Curated official German geodata presets for the internal source manager."""

LICENSE_URL="https://www.govdata.de/dl-de/by-2-0"
BKG_ATTRIBUTION="© GeoBasis-DE / BKG · dl-de/by-2-0"

OGC_PRESETS=[
    {
        "id":"bkg-topplusopen-wms",
        "name":"BKG TopPlusOpen WMS",
        "kind":"wms",
        "url":"https://sgx.geodatenzentrum.de/wms_topplus_open",
        "layer":"web",
        "cache_allowed":True,
        "interval_minutes":1440,
        "provider":"Bundesamt für Kartographie und Geodäsie (BKG)",
        "attribution":BKG_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"Amtliche, deutschlandweite Webkarte TopPlusOpen. Der BKG-Dienst dokumentiert auch Offline-Nutzung unter Quellenvermerk.",
    },
    {
        "id":"bkg-topplusopen-wmts",
        "name":"BKG TopPlusOpen WMTS",
        "kind":"wmts",
        "url":"https://sgx.geodatenzentrum.de/wmts_topplus_open",
        "tile_url":"https://sgx.geodatenzentrum.de/wmts_topplus_open/tile/1.0.0/web/default/WEBMERCATOR/{z}/{y}/{x}.png",
        "layer":"web",
        "cache_allowed":True,
        "interval_minutes":1440,
        "provider":"Bundesamt für Kartographie und Geodäsie (BKG)",
        "attribution":BKG_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"TopPlusOpen als WMTS in Web Mercator. Für den Offline-Cache ist eine explizite Tile-Vorlage hinterlegt.",
    },
    {
        "id":"bkg-vg250-wms",
        "name":"BKG Verwaltungsgebiete VG250 WMS",
        "kind":"wms",
        "url":"https://sgx.geodatenzentrum.de/wms_vg250",
        "layer":"vg250_lan",
        "cache_allowed":False,
        "interval_minutes":43200,
        "provider":"Bundesamt für Kartographie und Geodäsie (BKG)",
        "attribution":BKG_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"Amtliche Verwaltungsgebiete Deutschlands (VG250), voreingestellt auf Ländergrenzen. Caching bleibt bewusst deaktiviert.",
    },
    {
        "id":"bkg-vg250-wfs",
        "name":"BKG Verwaltungsgebiete VG250 WFS",
        "kind":"wfs",
        "url":"https://sgx.geodatenzentrum.de/wfs_vg250",
        "layer":"vg250_gem",
        "cache_allowed":False,
        "interval_minutes":43200,
        "provider":"Bundesamt für Kartographie und Geodäsie (BKG)",
        "attribution":BKG_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"Amtliche Verwaltungsgebiete Deutschlands (VG250), voreingestellt auf Gemeinden; geeignet für periodische PostGIS-Synchronisierung.",
    },
]


def get_preset(preset_id):
    return next((preset for preset in OGC_PRESETS if preset["id"]==preset_id),None)
