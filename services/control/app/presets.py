"""Curated official German geodata presets for the internal source manager."""

LICENSE_URL="https://www.govdata.de/dl-de/by-2-0"
TOPPLUS_ATTRIBUTION='© <a href="https://www.bkg.bund.de">BKG</a> · <a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a> · <a href="https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_topplusopen.html">Datenquellen</a>'
VG_ATTRIBUTION='© GeoBasis-DE / <a href="https://www.bkg.bund.de">BKG</a> · <a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a>'

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
        "attribution":TOPPLUS_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"Amtliche, deutschlandweite Webkarte TopPlusOpen. BKG erlaubt Offline-Speicherung unter Quellenvermerk; bei Offline-Nutzung ist zusätzlich der datumsbezogene Datenquellenhinweis zu beachten.",
    },
    {
        "id":"bkg-topplusopen-wmts",
        "name":"BKG TopPlusOpen WMTS",
        "kind":"wmts",
        "url":"https://sgx.geodatenzentrum.de/wmts_topplus_open",
        "capabilities_url":"https://sgx.geodatenzentrum.de/wmts_topplus_open/1.0.0/WMTSCapabilities.xml",
        "tile_url":"https://sgx.geodatenzentrum.de/wmts_topplus_open/tile/1.0.0/web/default/WEBMERCATOR/{z}/{y}/{x}.png",
        "layer":"web",
        "cache_allowed":True,
        "interval_minutes":1440,
        "provider":"Bundesamt für Kartographie und Geodäsie (BKG)",
        "attribution":TOPPLUS_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"TopPlusOpen als WMTS in Web Mercator. Für Layer-Prüfung und Offline-Cache sind die offiziellen Capabilities- bzw. Tile-URLs getrennt hinterlegt; der datumsbezogene Offline-Quellenvermerk bleibt zu beachten.",
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
        "attribution":VG_ATTRIBUTION,
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
        "attribution":VG_ATTRIBUTION,
        "license_url":LICENSE_URL,
        "description":"Amtliche Verwaltungsgebiete Deutschlands (VG250), voreingestellt auf Gemeinden; geeignet für periodische PostGIS-Synchronisierung.",
    },
]


def get_preset(preset_id):
    return next((preset for preset in OGC_PRESETS if preset["id"]==preset_id),None)
