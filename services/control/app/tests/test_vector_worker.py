import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class VectorWorkerTests(unittest.TestCase):
    def test_prepare_area_extract_uses_polygon_and_complete_ways(self):
        import app.worker as worker
        with tempfile.TemporaryDirectory() as tmp:
            old=worker.OSM;worker.OSM=Path(tmp);(worker.OSM/"latest.osm.pbf").write_bytes(b"source")
            payload={"area_id":"Area-1","geojson":{"type":"Polygon","coordinates":[[[8.0,48.0],[9.0,48.0],[9.0,49.0],[8.0,48.0]]]}}
            commands=[]
            def fake_run(command,log_path,timeout,cancelled,label=""):
                commands.append(command)
                output=Path(command[command.index("--output")+1]);output.write_bytes(b"extract")
                return 0
            try:
                with patch("app.worker._run_cancellable",side_effect=fake_run),patch("app.worker.subprocess.run") as check:
                    extract,polygon,log=worker.prepare_area_extract(payload,lambda *_:None,lambda:False)
                command=commands[0]
                self.assertEqual(command[:2],["osmium","extract"])
                self.assertIn("--polygon",command);self.assertIn("--set-bounds",command)
                self.assertEqual(command[command.index("--strategy")+1],"complete_ways")
                document=json.loads(polygon.read_text())
                self.assertEqual(document["type"],"Feature")
                self.assertEqual(document["geometry"]["type"],"Polygon")
                self.assertEqual(extract.read_bytes(),b"extract")
                self.assertEqual(check.call_args.args[0][:3],["osmium","fileinfo","--check"])
                extract.unlink();polygon.unlink();log.unlink(missing_ok=True)
            finally:worker.OSM=old

    def test_legacy_queued_job_loads_geometry_from_config(self):
        import app.store as store,app.worker as worker
        with tempfile.TemporaryDirectory() as tmp:
            old_root=store.ROOT
            try:
                store.ROOT=Path(tmp)/"config"
                geom={"type":"Polygon","coordinates":[[[8,48],[9,48],[9,49],[8,48]]]}
                store.write_config({"areas":[{"id":"a1","name":"Area","geojson":geom}],"sources":[],"styles":[],"settings":{}})
                resolved,bbox=worker.area_geometry({"area_id":"a1","bbox":[8,48,9,49]})
                self.assertEqual(resolved,geom);self.assertEqual(bbox,[8,48,9,49])
            finally:store.ROOT=old_root

    def test_vector_payload_carries_validated_geometry(self):
        import app.store as store,app.main as main
        with tempfile.TemporaryDirectory() as tmp:
            old_root=store.ROOT
            try:
                store.ROOT=Path(tmp)/"config"
                geom={"type":"Polygon","coordinates":[[[8,48],[9,48],[9,49],[8,48]]]}
                store.write_config({"areas":[{"id":"a1","name":"Area","geojson":geom}],"sources":[],"styles":[],"settings":{}})
                payload=main.vector_payload("a1")
                self.assertEqual(payload["geojson"],geom)
                self.assertEqual(payload["bbox"],[8,48,9,49])
            finally:store.ROOT=old_root

if __name__=="__main__":unittest.main()
