import tempfile,unittest
from pathlib import Path

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
        self.assertTrue(wmts["cache_allowed"])
        self.assertFalse(next(p for p in OGC_PRESETS if p["id"]=="bkg-vg250-wfs")["cache_allowed"])

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

if __name__=="__main__":unittest.main()
