"""Neu AI self-hosted meeting-bot worker (reference implementation).

This is the service Neu's `SelfHostedBotProvider` talks to when
BOT_PROVIDER=selfhosted. It exposes the tiny HTTP contract the backend expects:

    POST /bots                 {meeting_url, bot_name} -> {id, status}
    GET  /bots/{id}            -> {status}
    GET  /bots/{id}/recording  -> {audio_url, audio_ext, speakers[]}
    GET  /bots/{id}/audio      -> the recorded audio bytes
    GET  /health               -> {ok, mode}

Statuses use Neu's normalized vocabulary directly:
    joining | recording | done | failed | left

Modes (SELFBOT_MODE):
  * mock  (default, Phase 1) — no browser. Simulates a bot that joins, records
    for a few seconds, then finishes, handing back a bundled demo recording.
    This proves the whole invite -> record -> transcribe -> summarize path
    without any Recall.ai account or headless browser.
  * meet  (Phase 2) — a headless-Chromium (Playwright) bot that actually joins
    Google Meet and captures the call audio. Not implemented yet; the seam is
    here so adding it changes nothing in the Neu backend.

Auth: if SELFBOT_TOKEN is set, every control endpoint requires
`Authorization: Bearer <token>` (must match the backend's SELFBOT_TOKEN). The
/audio endpoint is intentionally unauthenticated so the backend can stream the
recording from a one-time internal URL — keep this worker on a private network
or behind your reverse proxy.
"""

import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

MODE = os.getenv("SELFBOT_MODE", "mock").lower()
TOKEN = os.getenv("SELFBOT_TOKEN", "")
# URL at which the backend can reach THIS worker (used to build audio_url).
PUBLIC_URL = os.getenv("SELFBOT_PUBLIC_URL", "http://localhost:8080").rstrip("/")
# Mock timing — how long the simulated join / recording phases last.
JOIN_SECONDS = float(os.getenv("SELFBOT_MOCK_JOIN_SECONDS", "3"))
RECORD_SECONDS = float(os.getenv("SELFBOT_MOCK_RECORD_SECONDS", "6"))
# Recording the mock worker hands back.
DEMO_WAV = Path(os.getenv("SELFBOT_DEMO_WAV", "/data/demo_meeting.wav"))

app = FastAPI(title="Neu AI self-hosted bot worker")

# In-memory job table. A production (Phase 2) worker would persist this and
# track a real browser session per job.
_jobs: dict[str, dict] = {}


class CreateBot(BaseModel):
    meeting_url: str
    bot_name: str = "Neu AI Notetaker"


def _check_auth(authorization: str | None) -> None:
    if TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(403, "Invalid bot worker token")


def _status_for(job: dict) -> str:
    """Current normalized status for a job."""
    if MODE != "mock":
        # A real worker sets job["status"] as the browser session progresses.
        return job.get("status", "joining")
    elapsed = time.monotonic() - job["created"]
    if elapsed < JOIN_SECONDS:
        return "joining"
    if elapsed < JOIN_SECONDS + RECORD_SECONDS:
        return "recording"
    return "done"


@app.get("/health")
def health() -> dict:
    return {"ok": True, "mode": MODE}


@app.post("/bots")
def create_bot(body: CreateBot, authorization: str | None = Header(None)) -> dict:
    _check_auth(authorization)
    bot_id = uuid.uuid4().hex
    _jobs[bot_id] = {
        "created": time.monotonic(),
        "meeting_url": body.meeting_url,
        "bot_name": body.bot_name,
        "status": "joining",
    }
    # Phase 2: launch the headless-Chromium join here.
    return {"id": bot_id, "status": "joining"}


@app.get("/bots/{bot_id}")
def get_status(bot_id: str, authorization: str | None = Header(None)) -> dict:
    _check_auth(authorization)
    job = _jobs.get(bot_id)
    if job is None:
        raise HTTPException(404, "Unknown bot id")
    return {"status": _status_for(job)}


@app.get("/bots/{bot_id}/recording")
def get_recording(bot_id: str, authorization: str | None = Header(None)) -> dict:
    _check_auth(authorization)
    job = _jobs.get(bot_id)
    if job is None:
        raise HTTPException(404, "Unknown bot id")
    if _status_for(job) != "done":
        raise HTTPException(409, "Recording not ready")
    return {
        "audio_url": f"{PUBLIC_URL}/bots/{bot_id}/audio",
        "audio_ext": ".wav",
        # A real worker fills this from participant events for real speaker names.
        "speakers": [],
    }


@app.get("/bots/{bot_id}/audio")
def get_audio(bot_id: str) -> FileResponse:
    if bot_id not in _jobs:
        raise HTTPException(404, "Unknown bot id")
    if not DEMO_WAV.exists():
        raise HTTPException(404, f"Recording not found at {DEMO_WAV}")
    return FileResponse(DEMO_WAV, media_type="audio/wav", filename="recording.wav")
