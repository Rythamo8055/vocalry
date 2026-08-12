import asyncio
import io
import json
import shutil
import time
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import asynccontextmanager

import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker._task = asyncio.create_task(worker.worker_loop())
    yield

app = FastAPI(title="8D Studio", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

worker.init_db()

app.mount("/static", StaticFiles(directory=worker.APP_DIR / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    return (worker.APP_DIR / "static" / "index.html").read_text()

def job_payload(row):
    jdir = worker.JOBS_DIR / row["id"]
    outputs = []
    if row["status"] == "done":
        for p in sorted(jdir.glob("*.wav")) + sorted(jdir.glob("*.mp3")):
            if p.name.startswith("input.") or p.name == "8d_mix.wav":
                continue
            outputs.append(p.name)
    return {
        "id": row["id"],
        "name": row["name"],
        "stems": json.loads(row["stems"]),
        "model": row["model"],
        "make_8d": bool(row["make_8d"]),
        "status": row["status"],
        "progress": row["progress"],
        "error": row["error"],
        "created": row["created"],
        "finished": row["finished"],
        "outputs": outputs,
    }

@app.get("/api/jobs")
async def list_jobs():
    con = worker.db()
    rows = con.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 50").fetchall()
    con.close()
    return [job_payload(dict(r)) for r in rows]

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    row = worker.job_row(jid)
    if not row:
        raise HTTPException(404, "job not found")
    return job_payload(row)

@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...), stems: str = Form("all"), make_8d: str = Form("0")):
    if worker.queue_depth() >= worker.MAX_QUEUE:
        raise HTTPException(429, f"queue full (max {worker.MAX_QUEUE}) — wait for a job to finish")
    name = file.filename or "song.mp3"
    suffix = Path(name).suffix.lower()
    if suffix not in {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}:
        raise HTTPException(400, f"unsupported format {suffix}")
    stem_list = [s.strip().lower() for s in stems.split(",") if s.strip()]
    if "all" in stem_list or not stem_list:
        stem_list = worker.ALL_STEMS
    if "instrumental" not in stem_list and len(stem_list) > 1:
        pass
    valid = set(worker.ALL_STEMS + ["instrumental"])
    bad = set(stem_list) - valid
    if bad:
        raise HTTPException(400, f"unknown stems: {sorted(bad)}")
    jid = uuid.uuid4().hex[:12]
    out_dir = worker.JOBS_DIR / jid
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"input{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    worker.create_job(jid, name, stem_list, make_8d == "1")
    return job_payload(worker.job_row(jid))

@app.get("/api/jobs/{jid}/files/{fname}")
async def download(jid: str, fname: str):
    row = worker.job_row(jid)
    if not row:
        raise HTTPException(404, "job not found")
    path = worker.JOBS_DIR / jid / fname
    if not path.exists() or path.is_dir():
        raise HTTPException(404, "file not found")
    safe = Path(fname).name
    clean = Path(row["name"]).stem
    return FileResponse(path, filename=f"{clean}_{safe}")

@app.get("/api/jobs/{jid}/zip")
async def download_zip(jid: str):
    row = worker.job_row(jid)
    if not row:
        raise HTTPException(404, "job not found")
    jdir = worker.JOBS_DIR / jid
    files = [p for p in list(jdir.glob("*.wav")) + list(jdir.glob("*.mp3")) if p.name not in {"input.mp3", "8d_mix.wav"}]
    if not files:
        raise HTTPException(404, "no output files yet")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname=f"{Path(row['name']).stem}/{p.name}")
    buf.seek(0)
    return io.BytesIO(buf.getvalue())

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
