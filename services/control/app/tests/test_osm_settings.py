import tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class OSMSettingsTests(unittest.TestCase):
    def test_settings_are_persisted_and_schedule_is_reset(self):
        import app.store as store,app.main as main,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                store.write_config({"areas":[],"sources":[],"styles":[],"settings":{}})
                with store.connect() as db:
                    scheduler.ensure_table(db);db.execute("INSERT INTO schedules(source_id,last_run,next_run) VALUES('__osm_snapshot__',1,2)")
                value=main.OSMSettings(osm_auto_refresh=True,osm_refresh_hours=8,osm_pbf_url="https://example.com/region.osm.pbf",osm_replication_url="https://example.com/updates/")
                with patch("app.main.validate_url",side_effect=lambda value:value):result=main.put_osm_settings(value)
                self.assertTrue(result["osm_auto_refresh"]);self.assertEqual(result["osm_refresh_hours"],8)
                self.assertEqual(store.read_config()["settings"]["osm_replication_url"],"https://example.com/updates/")
                with store.connect() as db:self.assertIsNone(db.execute("SELECT 1 FROM schedules WHERE source_id='__osm_snapshot__'").fetchone())
            finally:store.DB,store.ROOT=old_db,old_root

    def test_manual_refresh_forces_scheduler(self):
        import app.main as main
        with patch("app.main.effective_osm_settings",return_value={"osm_pbf_url":"https://example.com/region.osm.pbf"}),patch("app.main.enqueue_osm_refresh",return_value=1) as enqueue:
            self.assertEqual(main.refresh_osm(),{"queued":1});enqueue.assert_called_once_with(force=True)

if __name__=="__main__":unittest.main()
