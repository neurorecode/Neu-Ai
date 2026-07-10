"""End-to-end API tests: upload -> pipeline -> edit -> rename -> resummarize.

Uses the mock STT provider and the no-key summary fallback, exercising the
real job queue and worker through the app lifespan.
"""

import subprocess
import time

import pytest

from app.services.audio import ffmpeg_available


def _make_tone(tmp_path, seconds=3) -> str:
    path = tmp_path / "tone.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-ar", "16000", "-ac", "1", str(path),
        ],
        check=True,
    )
    return str(path)


def _wait_for_status(client, meeting_id, wanted, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = client.get(f"/api/meetings/{meeting_id}").json()
        if detail["status"] in wanted:
            return detail
        time.sleep(0.5)
    raise AssertionError(f"Meeting never reached {wanted}; last: {detail['status']} ({detail.get('stage')})")


@pytest.fixture()
def completed_meeting(client, tmp_path):
    audio = _make_tone(tmp_path) if ffmpeg_available() else None
    if audio:
        files = {"file": ("tone.wav", open(audio, "rb"), "audio/wav")}
    else:
        files = {"file": ("tone.wav", b"fake", "audio/wav")}
    resp = client.post("/api/meetings", data={"title": "API test meeting"}, files=files)
    assert resp.status_code == 201, resp.text
    meeting = resp.json()
    assert meeting["progress"] == 0
    return _wait_for_status(client, meeting["id"], {"completed"})


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["stt_provider"] == "mock"


def test_created_at_is_utc(completed_meeting):
    # Must carry an explicit UTC offset, else browsers parse it as local time.
    ts = completed_meeting["created_at"]
    assert ts.endswith("+00:00") or ts.endswith("Z"), ts


def test_full_pipeline(completed_meeting, client):
    detail = completed_meeting
    assert detail["progress"] == 100
    assert detail["language"] == "tanglish"  # mock transcript is code-mixed
    assert len(detail["segments"]) > 5
    assert all(s["language"] for s in detail["segments"])
    assert detail["summary"] is not None  # no-key fallback summary

    # Search finds transcript content
    hits = client.get("/api/meetings/search", params={"q": "Redis"}).json()
    assert any(h["meeting_id"] == detail["id"] for h in hits)


def test_segment_edit_updates_language_and_search(completed_meeting, client):
    meeting_id = completed_meeting["id"]
    segment = completed_meeting["segments"][0]

    resp = client.patch(
        f"/api/meetings/{meeting_id}/segments/{segment['id']}",
        json={"text": "This is now a corrected plain English sentence about zebras."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["language"] == "english"  # re-detected after the edit

    hits = client.get("/api/meetings/search", params={"q": "zebras"}).json()
    assert any(h["segment_id"] == segment["id"] for h in hits)

    # Empty edit rejected
    resp = client.patch(
        f"/api/meetings/{meeting_id}/segments/{segment['id']}", json={"text": "   "}
    )
    assert resp.status_code == 400


def test_speaker_rename(completed_meeting, client):
    meeting_id = completed_meeting["id"]
    old = completed_meeting["segments"][0]["speaker"]
    assert old  # mock transcript has speakers

    resp = client.post(
        f"/api/meetings/{meeting_id}/speakers/rename",
        json={"from_name": old, "to_name": "Renamed Person"},
    )
    assert resp.status_code == 200
    segments = resp.json()
    assert any(s["speaker"] == "Renamed Person" for s in segments)
    assert not any(s["speaker"] == old for s in segments)

    resp = client.post(
        f"/api/meetings/{meeting_id}/speakers/rename",
        json={"from_name": "Nobody", "to_name": "X"},
    )
    assert resp.status_code == 404


def test_resummarize(completed_meeting, client):
    meeting_id = completed_meeting["id"]
    resp = client.post(f"/api/meetings/{meeting_id}/resummarize")
    assert resp.status_code == 200
    detail = _wait_for_status(client, meeting_id, {"completed"})
    assert detail["summary"] is not None
    # Transcript untouched by summarize-only job
    assert len(detail["segments"]) == len(completed_meeting["segments"])


def test_upload_rejects_unknown_extension(client):
    resp = client.post(
        "/api/meetings",
        data={"title": "bad"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_delete_meeting(completed_meeting, client):
    meeting_id = completed_meeting["id"]
    assert client.delete(f"/api/meetings/{meeting_id}").status_code == 204
    assert client.get(f"/api/meetings/{meeting_id}").status_code == 404
