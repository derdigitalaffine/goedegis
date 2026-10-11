import tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class SchedulerTests(unittest.TestCase):
    def _paths(self):
        import app.store as store
        return store,store.DB,store.ROOT

    def test_due_wfs_is_enqueued_once(self):
        import app.store as store,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                store.write_config({"areas":[],"styles":[],"settings":{},"sources":[{"id":"abc","name":"Example","kind":"wfs","url":"https://example.com/wfs","enabled":True,"interval_minutes":15}]})
                now=1000000
                self.assertEqual(scheduler.enqueue_due(now),1)
                self.assertEqual(scheduler.enqueue_due(now+10),0)
                rows=store.jobs();self.assertEqual(len(rows),1);self.assertEqual(rows[0]["type"],"wfs_sync")
            finally:store.DB,store.ROOT=old_db,old_root

    def test_osm_refresh_is_enqueued_once_per_interval(self):
        import app.store as store,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                cfg={"areas":[],"styles":[],"sources":[],"settings":{"osm_auto_refresh":True,"osm_refresh_hours":6,"osm_pbf_url":"https://example.com/region.osm.pbf"}}
                store.write_config(cfg);now=2000000
                self.assertEqual(scheduler.enqueue_due(now),1)
                self.assertEqual(scheduler.enqueue_due(now+60),0)
                row=store.jobs()[0];self.assertEqual(row["type"],"download_osm");self.assertIn('"rebuild_vectors": true',row["payload"])
            finally:store.DB,store.ROOT=old_db,old_root

if __name__=="__main__":unittest.main()
