import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

class SchedulerTests(unittest.TestCase):
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
            finally:
                store.DB,store.ROOT=old_db,old_root

if __name__=="__main__":unittest.main()
