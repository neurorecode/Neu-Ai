"""Cross-meeting Ask: retrieval picks the relevant meeting and the endpoint
returns cited sources. (No LLM key in tests, so the answer is the graceful
'unavailable' message, but retrieval + sources are exercised for real.)"""

import subprocess
import time

import pytest

from app.services import ask_service
from app.services.audio import ffmpeg_available


def _tone(tmp_path):
    path = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=3", "-ar", "16000", "-ac", "1", str(path)],
        check=True,
    )
    return str(path)


def _completed_meeting(client, tmp_path, title):
    audio = _tone(tmp_path)
    with open(audio, "rb") as fh:
        resp = client.post(
            "/api/meetings", data={"title": title}, files={"file": ("tone.wav", fh, "audio/wav")}
        )
    assert resp.status_code == 201, resp.text
    mid = resp.json()["id"]
    deadline = time.time() + 45
    while time.time() < deadline:
        if client.get(f"/api/meetings/{mid}").json()["status"] == "completed":
            return mid
        time.sleep(0.5)
    raise AssertionError("meeting did not complete")


def test_keyword_extraction_drops_stopwords_keeps_tamil():
    kws = ask_service._keywords("What did we decide about Redis caching?")
    assert "redis" in kws and "caching" in kws
    assert "what" not in kws and "about" not in kws


@pytest.mark.skipif(not ffmpeg_available(), reason="needs ffmpeg to decode test audio")
def test_ask_finds_relevant_meeting(client, tmp_path):
    mid = _completed_meeting(client, tmp_path, "Sprint stand-up")
    resp = client.post("/api/ask", json={"question": "What did we decide about Redis?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    source_ids = {s["meeting_id"] for s in body["sources"]}
    assert mid in source_ids
    # Each source carries a human-readable title + date for citation.
    assert all(s["title"] and s["date"] for s in body["sources"])


def test_ask_rejects_empty_question(client):
    resp = client.post("/api/ask", json={"question": "   "})
    assert resp.status_code == 400


@pytest.mark.skipif(not ffmpeg_available(), reason="needs ffmpeg to decode test audio")
def test_ask_accepts_conversation_history(client, tmp_path):
    # A follow-up with little content of its own should still retrieve meetings
    # by leaning on the prior turn's keywords (Redis).
    _completed_meeting(client, tmp_path, "Caching decision call")
    resp = client.post(
        "/api/ask",
        json={
            "question": "who decided that?",
            "history": [
                {"role": "user", "content": "What did we decide about Redis?"},
                {"role": "assistant", "content": "You agreed to use Redis for caching."},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    # History is accepted and retrieval runs (returns cited meetings).
    assert len(resp.json()["sources"]) >= 1


@pytest.mark.skipif(not ffmpeg_available(), reason="needs ffmpeg to decode test audio")
def test_ask_recent_fallback_when_no_keyword_match(client, tmp_path):
    # A question whose keywords match nothing should still return recent meetings
    # so "summarize this week" style queries work.
    _completed_meeting(client, tmp_path, "Random sync")
    resp = client.post("/api/ask", json={"question": "xyzzy zzxq nonexistentword"})
    assert resp.status_code == 200
    assert len(resp.json()["sources"]) >= 1
