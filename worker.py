import asyncio
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
_RES = Path(getattr(sys, "_MEIPASS", APP_DIR.parent / "renderer"))
JOBS_DIR = Path(os.environ.get("JOBS_DIR", APP_DIR / "jobs"))
DB_PATH = Path(os.environ.get("DB_PATH", APP_DIR / "jobs.db"))
MODEL_DIR = Path(os.environ.get("MODEL_DIR", Path.home() / ".audio-separator" / "models"))
HRTF_ZIP = Path(os.environ.get("HRTF_ZIP", _RES / "hrtf" / "full.zip"))
RENDER_SCRIPT = Path(os.environ.get("RENDER_SCRIPT", _RES / "8d_render.py"))
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", shutil.which("ffmpeg") or "ffmpeg")

MAX_QUEUE = 5

ALL_STEMS = ["vocals", "drums", "bass", "other", "guitar", "piano"]

FOR_MODEL = {
    "htdemucs_6s.yaml": {"vocals", "drums", "bass", "guitar", "piano", "other"},
    "htdemucs_ft.yaml": {"vocals", "drums", "bass", "other"},
}

def model_for(stems):
    need = set(stems)
    if need == {"vocals", "instrumental"}:
        return "MDX23C-8KFFT-InstVoc_HQ.ckpt"
    if need <= FOR_MODEL["htdemucs_6s.yaml"] and ({"guitar", "piano"} & need):
        return "htdemucs_6s.yaml"
    if need <= FOR_MODEL["htdemucs_ft.yaml"]:
        return "htdemucs_ft.yaml"
    if need - {"vocals", "drums", "bass", "other"} == set():
        return "htdemucs_ft.yaml"
    return "htdemucs_6s.yaml"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute(
        "CREATE TABLE IF NOT EXISTS jobs ("
        "id TEXT PRIMARY KEY, name TEXT, stems TEXT, model TEXT, make_8d INTEGER,"
        "status TEXT, progress REAL, error TEXT, output_dir TEXT, created REAL, finished REAL)"
    )
    con.commit()
    con.close()

def job_row(jid):
    con = db()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    con.close()
    return dict(row) if row else None

def update_job(jid, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    con = db()
    con.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*fields.values(), jid))
    con.commit()
    con.close()

def create_job(jid, name, stems, make_8d):
    con = db()
    con.execute(
        "INSERT INTO jobs (id, name, stems, model, make_8d, status, progress, error, output_dir, created, finished)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (jid, name, json.dumps(stems), model_for(stems), int(make_8d), "queued", 0.0, None, None, time.time(), None),
    )
    con.commit()
    con.close()

def queue_depth():
    con = db()
    n = con.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
    con.close()
    return n

def filter_outputs(out_dir, stems):
    produced = {}
    for f in out_dir.glob("*.wav"):
        if f.name.startswith("input.") or f.name == "8d_mix.wav":
            continue
        for stem in ALL_STEMS:
            if f"({stem.capitalize()})" in f.name:
                produced[stem] = f
                break
        if "(Instrumental)" in f.name:
            produced["instrumental"] = f
    wanted = set(stems)
    for stem, path in produced.items():
        if stem not in wanted:
            path.unlink(missing_ok=True)
    return {s: p for s, p in produced.items() if s in wanted}

def separate_in_process(input_path, out_dir, model, jid):
    from audio_separator.separator import Separator
    sep = Separator(
        model_file_dir=str(MODEL_DIR),
        output_dir=str(out_dir),
        output_format="WAV",
        log_level=logging.ERROR,
    )
    sep.load_model(model_filename=model)
    sep.separate(str(input_path))

def render_8d(out_dir):
    import importlib.util
    spec = importlib.util.spec_from_file_location("render8d", RENDER_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.render(str(out_dir), str(out_dir / "8d_mix.wav"), str(HRTF_ZIP))

async def make_8d_mix(job, out_dir, jid):
    stems = json.loads(job["stems"])
    if "instrumental" in stems:
        return
    await asyncio.to_thread(render_8d, out_dir)
    mix = out_dir / "8d_mix.wav"
    if mix.exists():
        ff = await asyncio.create_subprocess_exec(
            FFMPEG_BIN, "-y", "-loglevel", "error", "-i", str(mix),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "libmp3lame", "-b:a", "320k", str(out_dir / "8d_mix.mp3"),
        )
        await ff.wait()
        mix.unlink(missing_ok=True)

async def worker_loop():
    while True:
        con = db()
        row = con.execute(
            "SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1"
        ).fetchone()
        con.close()
        if not row:
            await asyncio.sleep(1.5)
            continue
        job = dict(row)
        jid = job["id"]
        out_dir = JOBS_DIR / jid
        out_dir.mkdir(parents=True, exist_ok=True)
        update_job(jid, status="running")
        try:
            input_files = sorted(out_dir.glob("input.*"))
            input_path = input_files[0] if input_files else out_dir / "input.mp3"
            update_job(jid, progress=5.0)
            await asyncio.to_thread(separate_in_process, input_path, out_dir, job["model"], jid)
            update_job(jid, progress=90.0)
            produced = filter_outputs(out_dir, json.loads(job["stems"]))
            if job["make_8d"]:
                update_job(jid, progress=95.0)
                await make_8d_mix(job, out_dir, jid)
            update_job(jid, status="done", progress=100.0, finished=time.time())
        except Exception as exc:
            logging.exception("job %s failed", jid)
            update_job(jid, status="failed", error=str(exc), finished=time.time())
