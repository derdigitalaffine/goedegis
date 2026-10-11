import tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class PresetTests(unittest.TestCase):
    def test_catalog_is_unique_and_uses_official_https_endpoints(self):
        from app.presets import OGC_PRESETS
        ids=[p["id"] for p in OGC_PRESETS]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(ids),4)
        for preset in OGC_PRESETS:
            self.assertTrue(preset["url"].startswith("https://sgx.geodatenzentrum.de/"))
            self.assertTrue(preset["attribution"])
            self.assertTrue(preset["license_url"].startswith("https://"))
        wmts=next(p for p in OGC_PRESETS if p["id"]=="bkg-topplusopen-wmts")
        self.assertTrue(all(token in wmts["tile_url"] for token in ("{z}","{x}","{y}")))
        self.assertTrue(wmts["capabilities_url"].endswith("WMTSCapabilities.xml"))
        self.assertTrue(wmts["cache_allowed"])
        self.assertFalse(next(p for p in OGC_PRESETS if p["id"]=="bkg-vg250-wfs")["cache_allowed"])

    def test_explicit_wmts_capabilities_document_is_used_verbatim(self):
        from app.ogc import request_url
        explicit="https://example.com/wmts/1.0.0/WMTSCapabilities.xml"
        self.assertEqual(request_url(explicit,"wmts"),explicit)
        self.assertIn("REQUEST=GetCapabilities",request_url("https://example.com/wms","wms"))

    def test_install_is_idempotent(self):
        import app.store as store,app.main as main
        with tempfile.TemporaryDirectory() as tmp:
            old_root=store.ROOT
            try:
                store.ROOT=Path(tmp)/"config"
                store.write_config({"areas":[],"sources":[],"styles":[],"settings":{}})
                first=main.install_preset("bkg-topplusopen-wms")
                second=main.install_preset("bkg-topplusopen-wms")
                self.assertEqual(first["id"],second["id"])
                self.assertEqual(len(store.read_config()["sources"]),1)
                self.assertEqual(first["preset_id"],"bkg-topplusopen-wms")
            finally:store.ROOT=old_root

    def test_preset_status_reflects_installed_sources(self):
        import app.store as store,app.main as main
        with tempfile.TemporaryDirectory() as tmp:
            old_root=store.ROOT
            try:
                store.ROOT=Path(tmp)/"config"
                store.write_config({"areas":[],"sources":[],"styles":[],"settings":{}})
                self.assertFalse(next(p for p in main.ogc_presets() if p["id"]=="bkg-vg250-wfs")["installed"])
                main.install_preset("bkg-vg250-wfs")
                self.assertTrue(next(p for p in main.ogc_presets() if p["id"]=="bkg-vg250-wfs")["installed"])
            finally:store.ROOT=old_root

    def test_wmts_cache_prefers_preset_tile_url(self):
        import app.cache as cache
        with tempfile.TemporaryDirectory() as tmp:
            old_cache=cache.CACHE;cache.CACHE=Path(tmp)
            source={"id":"bkg_wmts","kind":"wmts","url":"https://example.com/capabilities","tile_url":"https://tiles.example.com/{z}/{y}/{x}.png","cache_allowed":True}
            area={"geojson":{"type":"Polygon","coordinates":[]},"zoom_min":1,"zoom_max":1}
            try:
                png=b"\x89PNG\r\n\x1a\nmock"
                with patch("app.cache.geometry",return_value=(object(),None)),patch("app.cache.tiles",return_value=iter([(1,0,1)])),patch("app.cache.validate_url"),patch("app.cache.get",return_value=(png,"image/png")) as fetch:
                    self.assertEqual(cache.run({"source":source,"area":area,"max_tiles":1}),"Cached 1 tiles")
                self.assertEqual(fetch.call_args.args[0],"https://tiles.example.com/1/1/0.png")
            finally:cache.CACHE=old_cache

if __name__=="__main__":unittest.main()
