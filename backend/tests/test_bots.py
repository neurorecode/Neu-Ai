"""Meeting-bot flow: invite (mock provider), webhook, and platform detection."""

import time

import pytest


@pytest.fixture(autouse=True)
def _enable_mock_bot(monkeypatch):
    # bots_enabled() checks provider=="recall"; for tests we force the invite
    # endpoint's gate open and use the mock provider under the hood.
    from app.services import bots as bots_pkg
    from app.routers import bots as bots_router

    monkeypatch.setattr(bots_pkg, "bots_enabled", lambda: True)
    monkeypatch.setattr(bots_router, "bots_enabled", lambda: True)
    from app.config import settings

    monkeypatch.setattr(settings, "bot_provider", "mock")
    yield


def _wait_completed(client, meeting_id, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = client.get(f"/api/meetings/{meeting_id}").json()
        if d["status"] in {"completed", "failed"}:
            return d
        time.sleep(0.5)
    raise AssertionError("bot meeting did not finish")


def test_invite_bot_rejects_non_meeting_url(client):
    resp = client.post("/api/meetings/invite-bot", json={"meeting_url": "https://example.com/foo"})
    assert resp.status_code == 400


def test_invite_bot_full_flow(client):
    resp = client.post(
        "/api/meetings/invite-bot",
        json={"meeting_url": "https://meet.google.com/abc-defg-hij", "title": "QA sync"},
    )
    assert resp.status_code == 201, resp.text
    meeting = resp.json()
    assert meeting["source"] == "bot"

    detail = _wait_completed(client, meeting["id"])
    assert detail["status"] == "completed"
    # Real participant names came from the bot speaker timeline
    speakers = {s["speaker"] for s in detail["segments"] if s["speaker"]}
    assert "Priya" in speakers and "Karthik" in speakers
    assert detail["language"] == "tanglish"

    bot = client.get(f"/api/meetings/{meeting['id']}/bot").json()
    assert bot["status"] == "done"
    assert bot["meeting_url"].startswith("https://meet.google.com/")


def test_webhook_rejects_bad_secret(client):
    resp = client.post("/api/bots/webhook/wrong-secret", json={"event": "bot.status_change"})
    assert resp.status_code == 403


def test_platform_detection():
    from app.routers.bots import _platform

    assert _platform("https://meet.google.com/abc-defg-hij") == "Google Meet"
    assert _platform("https://us02web.zoom.us/j/8412345678") == "Zoom"
    assert _platform("https://teams.microsoft.com/l/meetup-join/xyz") == "Microsoft Teams"
    assert _platform("https://example.com") is None
