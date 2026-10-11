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
    cols={r["name"] for r in db.execute("PRAGMA table_info(jobs)")}
    for name,definition in (
        ("attempts","INTEGER NOT NULL DEFAULT 0"),
        ("max_attempts","INTEGER NOT NULL DEFAULT 3"),
        ("next_run","REAL NOT NULL DEFAULT 0"),
        ("cancel_requested","INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in cols: db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
    return db

def read_config():
    ROOT.mkdir(parents=True, exist_ok=True)
    p=ROOT/"config.json"
    if not p.exists(): return json.loads(json.dumps(DEFAULT))
    return {**DEFAULT,**json.loads(p.read_text())}

def write_config(data):
    ROOT.mkdir(parents=True, exist_ok=True)
    p=ROOT/"config.json"
    tmp=p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False))
    tmp.replace(p)

def add_job(kind,payload,priority=0,max_attempts=3):
    job_id=str(uuid.uuid4())
    now=time.time()
    with connect() as db:
        db.execute("""INSERT INTO jobs
        (id,type,payload,state,priority,progress,message,created,updated,max_attempts,next_run)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id,kind,json.dumps(payload),"queued",int(priority),0,"",now,now,max_attempts,now))
    return job_id

def jobs():
    with connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 200")]

def change_job(job_id,action):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
        if not row: raise KeyError(job_id)
        state=row["state"]
        if action=="cancel":
            if state in ("queued","paused","retry_wait"): db.execute("UPDATE jobs SET state='cancelled',updated=? WHERE id=?",(time.time(),job_id))
            elif state=="running": db.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?",(job_id,))
            else: raise ValueError("Job cannot be cancelled in its current state")
        elif action=="pause":
            if state not in ("queued","retry_wait"): raise ValueError("Only queued jobs can be paused")
            db.execute("UPDATE jobs SET state='paused',updated=? WHERE id=?",(time.time(),job_id))
        elif action=="resume":
            if state!="paused": raise ValueError("Job is not paused")
            db.execute("UPDATE jobs SET state='queued',next_run=?,updated=? WHERE id=?",(time.time(),time.time(),job_id))
        elif action=="retry":
            if state not in ("failed","cancelled"): raise ValueError("Only failed/cancelled jobs can be retried")
            db.execute("UPDATE jobs SET state='queued',attempts=0,cancel_requested=0,next_run=?,updated=? WHERE id=?",(time.time(),time.time(),job_id))
        else: raise ValueError("Unknown action")
    return {"ok":True}
