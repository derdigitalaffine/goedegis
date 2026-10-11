import os,unittest
from unittest.mock import patch

class WFSWorkerTests(unittest.TestCase):
    def test_selected_layer_is_passed_to_ogr2ogr(self):
        import app.worker as worker
        payload={"url":"https://example.com/wfs","table":"vg250_gemeinden","layer":"vg250_gem"}
        with patch.dict(os.environ,{"POSTGRES_DSN":"postgresql://user:pass@db:5432/goedegis"}),patch("app.worker.validate_url",return_value=payload["url"]),patch("app.worker.subprocess.run") as run:
            self.assertEqual(worker.run_job("wfs_sync",payload),"WFS synchronized")
        command=run.call_args.args[0]
        self.assertIn("WFS:https://example.com/wfs",command)
        self.assertIn("vg250_gem",command)
        self.assertLess(command.index("WFS:https://example.com/wfs"),command.index("vg250_gem"))
        self.assertLess(command.index("vg250_gem"),command.index("-nln"))

    def test_invalid_layer_is_rejected(self):
        import app.worker as worker
        payload={"url":"https://example.com/wfs","table":"target","layer":"bad layer;drop"}
        with patch.dict(os.environ,{"POSTGRES_DSN":"postgresql://user:pass@db:5432/goedegis"}),patch("app.worker.validate_url",return_value=payload["url"]):
            with self.assertRaisesRegex(ValueError,"Invalid WFS layer"):worker.run_job("wfs_sync",payload)

if __name__=="__main__":unittest.main()
