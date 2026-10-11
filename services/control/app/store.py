import json, os, sqlite3, time, uuid
from pathlib import Path

ROOT = Path(os.getenv("GOEDEGIS_CONFIG_DIR", "/data/config"))
DB = Path(os.getenv("GOEDEGIS_JOB_DB", "/data/jobs/jobs.sqlite3"))
DEFAULT = {"areas": [], "sources": [], "styles": [], "settings": {"max_parallel_jobs": 1}}

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, type TEXT NOT NULL, payload TEXT NOT NULL,
        state TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0,
        progress REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
        created REAL NOT NULL, updated REAL NOT NULL)""")
    return db

def read_config():
    ROOT.mkdir(parents=True, exist_ok=True)
    p = ROOT / "config.json"
    if not p.exists():
        return json.loads(json.dumps(DEFAULT))
    return {**DEFAULT, **json.loads(p.read_text())}

def write_config(data):
    ROOT.mkdir(parents=True, exist_ok=True)
    p = ROOT / "config.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(p)

def add_job(kind, payload, priority=0):
    job_id = str(uuid.uuid4())
    now = time.time()
    with connect() as db:
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
            (job_id, kind, json.dumps(payload), "queued", int(priority), 0, "", now, now))
    return job_id

def jobs():
    with connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 200")]
