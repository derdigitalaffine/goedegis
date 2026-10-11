import tempfile,unittest
from pathlib import Path

class SchedulerTests(unittest.TestCase):
    def test_due_wfs_is_enqueued_once(self):
        import app.store as store,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                store.write_config({"areas":[],"styles":[],"settings":{},"sources":[{"id":"abc","name":"Example","kind":"wfs","url":"https://example.com/wfs","layer":"vg250_gem","enabled":True,"interval_minutes":15}]})
                now=1000000
                self.assertEqual(scheduler.enqueue_due(now),1);self.assertEqual(scheduler.enqueue_due(now+10),0)
                rows=store.jobs();self.assertEqual(len(rows),1);self.assertEqual(rows[0]["type"],"wfs_sync");self.assertIn('"layer": "vg250_gem"',rows[0]["payload"])
            finally:store.DB,store.ROOT=old_db,old_root

    def test_osm_refresh_is_enqueued_once_per_interval(self):
        import app.store as store,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                cfg={"areas":[],"styles":[],"sources":[],"settings":{"osm_auto_refresh":True,"osm_refresh_hours":6,"osm_pbf_url":"https://example.com/region.osm.pbf","osm_replication_url":"https://example.com/updates/"}}
                store.write_config(cfg);now=2000000
                self.assertEqual(scheduler.enqueue_due(now),1);self.assertEqual(scheduler.enqueue_due(now+60),0)
                row=store.jobs()[0];self.assertEqual(row["type"],"update_osm");self.assertIn('"rebuild_vectors": true',row["payload"]);self.assertIn('"replication_url": "https://example.com/updates/"',row["payload"])
            finally:store.DB,store.ROOT=old_db,old_root

    def test_force_refresh_works_when_auto_refresh_is_disabled(self):
        import app.store as store,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                store.write_config({"areas":[],"styles":[],"sources":[],"settings":{"osm_auto_refresh":False,"osm_pbf_url":"https://example.com/region.osm.pbf","osm_replication_url":"https://example.com/updates/"}})
                self.assertEqual(scheduler.enqueue_osm_refresh(now=3000000),0)
                self.assertEqual(scheduler.enqueue_osm_refresh(now=3000000,force=True),1)
                self.assertEqual(scheduler.enqueue_osm_refresh(now=3000010,force=True),0)
                self.assertEqual(store.jobs()[0]["type"],"update_osm")
            finally:store.DB,store.ROOT=old_db,old_root

    def test_reset_osm_schedule_allows_new_due_decision(self):
        import app.store as store,app.scheduler as scheduler
        with tempfile.TemporaryDirectory() as tmp:
            old_db,old_root=store.DB,store.ROOT
            try:
                store.DB=Path(tmp)/"jobs.sqlite3";store.ROOT=Path(tmp)/"config"
                cfg={"areas":[],"styles":[],"sources":[],"settings":{"osm_auto_refresh":True,"osm_refresh_hours":24,"osm_pbf_url":"https://example.com/region.osm.pbf"}}
                store.write_config(cfg);self.assertEqual(scheduler.enqueue_due(4000000),1)
                with store.connect() as db:db.execute("UPDATE jobs SET state='done'")
                scheduler.reset_osm_schedule()
                self.assertEqual(scheduler.enqueue_due(4000060),1)
            finally:store.DB,store.ROOT=old_db,old_root

if __name__=="__main__":unittest.main()
