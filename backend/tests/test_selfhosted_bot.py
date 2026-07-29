"""Phase 1 of the self-hosted meeting bot: prove the seam.

Neu's SelfHostedBotProvider talks to our own worker (selfbot/worker.py) over a
small HTTP contract. These tests verify provider selection, the contract
round-trip against the real worker app (via an in-process ASGI transport), the
local-file download branches, and the worker's own endpoints — all without a
browser or any Recall.ai account.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import httpx
import pytest

# Make the standalone worker importable and point its mock mode at the real
# demo recording with instant timings — must happen before importing worker.
DEMO_WAV = Path(__file__).resolve().parent / "data" / "demo_meeting.wav"
os.environ.setdefault("SELFBOT_DEMO_WAV", str(DEMO_WAV))
os.environ["SELFBOT_MOCK_JOIN_SECONDS"] = "0"
os.environ["SELFBOT_MOCK_RECORD_SECONDS"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "selfbot"))
import worker  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.bots import bots_enabled, get_bot_provider  # noqa: E402
from app.services.bots.download import download_recording  # noqa: E402
from app.services.bots.selfhosted import SelfHostedBotProvider  # noqa: E402


# --- provider selection & gating --------------------------------------------


def test_bots_enabled_tracks_selfbot_url(monkeypatch):
    monkeypatch.setattr(settings, "bot_provider", "selfhosted")
    monkeypatch.setattr(settings, "selfbot_url", "")
    assert bots_enabled() is False
    monkeypatch.setattr(settings, "selfbot_url", "http://selfbot:8080")
    assert bots_enabled() is True


def test_get_bot_provider_returns_selfhosted(monkeypatch):
    monkeypatch.setattr(settings, "bot_provider", "selfhosted")
    monkeypatch.setattr(settings, "selfbot_url", "http://selfbot:8080")
    assert isinstance(get_bot_provider(), SelfHostedBotProvider)


def test_provider_requires_a_worker_url():
    with pytest.raises(ValueError):
        SelfHostedBotProvider(worker_url="")


# --- HTTP contract round-trip against the real worker (ASGI, in-process) ------


def _provider_against_worker() -> SelfHostedBotProvider:
    transport = httpx.ASGITransport(app=worker.app)
    return SelfHostedBotProvider(worker_url="http://worker", transport=transport)


def test_contract_roundtrip_create_status_recording():
    provider = _provider_against_worker()

    async def go():
        handle = await provider.create_bot("https://meet.google.com/abc-defg-hij", "Neu AI", None)
        assert handle.provider_bot_id
        assert handle.status == "joining"

        # Mock timings are 0, so the job resolves to done right away.
        status = await provider.get_status(handle.provider_bot_id)
        assert status.status == "done"

        recording = await provider.fetch_recording(handle.provider_bot_id)
        assert recording.audio_ext == ".wav"
        assert recording.audio_url.endswith(f"/bots/{handle.provider_bot_id}/audio")
        return recording

    assert asyncio.run(go()) is not None


def test_status_normalizes_unknown_values():
    p = SelfHostedBotProvider(worker_url="http://x")
    assert p._normalize("recording") == "recording"
    assert p._normalize("weird") == "joining"
    assert p._normalize(None) == "joining"


# --- worker status progression (unit) ---------------------------------------


def test_worker_status_progression(monkeypatch):
    monkeypatch.setattr(worker, "MODE", "mock")
    monkeypatch.setattr(worker, "JOIN_SECONDS", 100.0)
    monkeypatch.setattr(worker, "RECORD_SECONDS", 100.0)

    now = time.monotonic()
    assert worker._status_for({"created": now}) == "joining"
    assert worker._status_for({"created": now - 150}) == "recording"
    assert worker._status_for({"created": now - 1000}) == "done"


# --- worker endpoints --------------------------------------------------------


def test_worker_serves_recording_bytes():
    from fastapi.testclient import TestClient

    client = TestClient(worker.app)
    created = client.post(
        "/bots", json={"meeting_url": "https://meet.google.com/x", "bot_name": "Neu"}
    )
    assert created.status_code == 200
    bot_id = created.json()["id"]

    audio = client.get(f"/bots/{bot_id}/audio")
    assert audio.status_code == 200
    assert len(audio.content) > 0


def test_worker_enforces_token(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(worker, "TOKEN", "s3cret")
    client = TestClient(worker.app)

    assert client.post("/bots", json={"meeting_url": "x"}).status_code == 403
    ok = client.post(
        "/bots",
        headers={"Authorization": "Bearer s3cret"},
        json={"meeting_url": "https://meet.google.com/x"},
    )
    assert ok.status_code == 200


# --- download branches (self-hosted worker sharing the upload volume) --------


def test_download_from_file_url(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    src = tmp_path / "src.wav"
    src.write_bytes(b"RIFFmockwavdata")

    dest = asyncio.run(download_recording("m1", f"file://{src}", ".wav"))
    assert Path(dest).name == "m1.wav"
    assert Path(dest).read_bytes() == b"RIFFmockwavdata"


def test_download_from_bare_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    src = tmp_path / "shared.wav"
    src.write_bytes(b"BAREpathbytes")

    dest = asyncio.run(download_recording("m2", str(src), ".wav"))
    assert Path(dest).read_bytes() == b"BAREpathbytes"
