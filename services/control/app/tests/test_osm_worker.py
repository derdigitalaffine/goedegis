import tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class OSMWorkerTests(unittest.TestCase):
    def test_update_uses_pyosmium_and_skips_rebuild_when_current(self):
        import app.worker as worker
        with tempfile.TemporaryDirectory() as tmp:
            old=worker.OSM;worker.OSM=Path(tmp);current=worker.OSM/"latest.osm.pbf";current.write_bytes(b"pbf")
            try:
                with patch("app.worker.validate_url",side_effect=lambda value:value),patch("app.worker._run_cancellable",return_value=0) as run,patch("app.worker.enqueue_vector_rebuilds") as rebuild:
                    result=worker.update_osm({"url":"https://example.com/region.osm.pbf","replication_url":"https://example.com/updates/","rebuild_vectors":True},lambda *_:None,lambda:False)
                self.assertEqual(result,"OSM data already current");self.assertEqual(run.call_args.args[0][0],"pyosmium-up-to-date");rebuild.assert_not_called()
            finally:worker.OSM=old

    def test_update_bootstraps_missing_replication_headers(self):
        import app.worker as worker
        with tempfile.TemporaryDirectory() as tmp:
            old=worker.OSM;worker.OSM=Path(tmp);(worker.OSM/"latest.osm.pbf").write_bytes(b"pbf")
            try:
                with patch("app.worker.validate_url",side_effect=lambda value:value),patch("app.worker._run_cancellable",side_effect=[2,0]) as run:
                    worker.update_osm({"url":"https://example.com/region.osm.pbf","replication_url":"https://example.com/updates/"},lambda *_:None,lambda:False)
                self.assertEqual(run.call_count,2);self.assertIn("--ignore-osmosis-headers",run.call_args_list[1].args[0])
            finally:worker.OSM=old

if __name__=="__main__":unittest.main()
