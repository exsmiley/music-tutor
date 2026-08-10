"""Transcription job-queue API.

Run:  .venv/bin/uvicorn server:app --port 8000
Jobs run one at a time in a worker thread; status lives in data/<id>/meta.json
so the queue survives restarts (running jobs become 'error: interrupted').

Endpoints (the Vite dev server proxies /api here):
  POST   /api/jobs                {"url": ..., "instruments": [...] | null}
  GET    /api/jobs                library, newest first
  GET    /api/jobs/{id}           status/progress/summary
  DELETE /api/jobs/{id}
  GET    /api/jobs/{id}/files/{name}   stem jsons, tabs, midi, source.mp3
"""

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline.run import run_pipeline, TRANSCRIBABLE

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="music-tutor transcription service")
executor = ThreadPoolExecutor(max_workers=1)
meta_lock = threading.Lock()

ALLOWED_FILES = re.compile(
    r"^(guitar|bass|vocals|other|piano|mix|drums)(-(L|R|lead|rhythm))?"
    r"\.(json|tab\.txt|mid)$|^(song\.mid|source\.mp3)$"
)


class JobRequest(BaseModel):
    url: str
    instruments: list[str] | None = None  # None = autodetect


def _meta_path(job_id: str) -> Path:
    return DATA_DIR / job_id / "meta.json"


def _read_meta(job_id: str) -> dict:
    path = _meta_path(job_id)
    if not path.exists():
        raise HTTPException(404, f"no such job: {job_id}")
    return json.loads(path.read_text())


def _write_meta(job_id: str, **updates) -> dict:
    with meta_lock:
        meta = json.loads(_meta_path(job_id).read_text())
        meta.update(updates)
        _meta_path(job_id).write_text(json.dumps(meta, indent=2))
        return meta


def _video_title(url: str) -> str:
    local = Path(url)
    if local.exists():
        return local.stem
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--no-playlist", "--print", "title", url],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return result.stdout.strip().splitlines()[0]
    except Exception:
        return url


def _run_job(job_id: str) -> None:
    job_dir = DATA_DIR / job_id
    meta = _read_meta(job_id)
    try:
        _write_meta(job_id, status="running", progress="starting")
        summary = run_pipeline(
            meta["url"],
            job_dir,
            instruments=meta.get("instruments"),
            progress=lambda msg: _write_meta(job_id, progress=msg),
        )
        _write_meta(job_id, status="done", progress="", summary=summary)
    except Exception as e:
        _write_meta(job_id, status="error", progress="", error=str(e)[:500])


@app.post("/api/jobs")
def create_job(req: JobRequest) -> dict:
    if req.instruments:
        unknown = set(req.instruments) - set(TRANSCRIBABLE)
        if unknown:
            raise HTTPException(400, f"unknown instruments: {sorted(unknown)}")
    job_id = uuid.uuid4().hex[:12]
    job_dir = DATA_DIR / job_id
    job_dir.mkdir()
    meta = {
        "id": job_id,
        "url": req.url,
        "title": _video_title(req.url),
        "instruments": req.instruments,
        "status": "queued",
        "progress": "",
        "created": time.time(),
    }
    _meta_path(job_id).write_text(json.dumps(meta, indent=2))
    executor.submit(_run_job, job_id)
    return meta


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    metas = []
    for meta_file in DATA_DIR.glob("*/meta.json"):
        try:
            metas.append(json.loads(meta_file.read_text()))
        except json.JSONDecodeError:
            continue
    return sorted(metas, key=lambda m: m.get("created", 0), reverse=True)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return _read_meta(job_id)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    import shutil

    job_dir = DATA_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, f"no such job: {job_id}")
    shutil.rmtree(job_dir)
    return {"deleted": job_id}


@app.get("/api/jobs/{job_id}/files/{name}")
def get_file(job_id: str, name: str) -> FileResponse:
    if not ALLOWED_FILES.match(name):
        raise HTTPException(400, f"file not allowed: {name}")
    path = DATA_DIR / job_id / name
    if not path.exists():
        raise HTTPException(404, f"file not found: {name}")
    media = {
        ".json": "application/json",
        ".txt": "text/plain",
        ".mid": "audio/midi",
        ".mp3": "audio/mpeg",
    }[path.suffix]
    return FileResponse(path, media_type=media)


# Jobs left 'running'/'queued' by a previous process will never finish.
for stale in list_jobs():
    if stale["status"] in ("running", "queued"):
        _write_meta(stale["id"], status="error", error="interrupted by server restart")
