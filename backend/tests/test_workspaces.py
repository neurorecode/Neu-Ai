"""Workspaces, invites, roles, sharing, and audio access."""

import subprocess
import time

import pytest

from app.services.audio import ffmpeg_available


def _upload(client, tmp_path, title="WS test meeting", workspace_id=None):
    if ffmpeg_available():
        path = tmp_path / "tone.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-ar", "16000", "-ac", "1", str(path)],
            check=True,
        )
        files = {"file": ("tone.wav", open(path, "rb"), "audio/wav")}
    else:
        files = {"file": ("tone.wav", b"fake", "audio/wav")}
    data = {"title": title}
    if workspace_id:
        data["workspace_id"] = workspace_id
    resp = client.post("/api/meetings", data=data, files=files)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _wait_completed(client, meeting_id, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = client.get(f"/api/meetings/{meeting_id}").json()
        if d["status"] in {"completed", "failed"}:
            return d
        time.sleep(0.5)
    raise AssertionError("meeting did not finish")


def test_dev_mode_me_and_default_workspace(client):
    me = client.get("/api/auth/me").json()
    assert me["email"] == "dev@localhost"

    workspaces = client.get("/api/workspaces").json()
    assert len(workspaces) >= 1
    assert workspaces[0]["role"] == "owner"


def test_auth_config_reports_dev_mode(client):
    assert client.get("/api/auth/config").json() == {"auth_enabled": False}
    # Login endpoint refuses in dev mode rather than redirecting nowhere
    assert client.get("/api/auth/google/login", follow_redirects=False).status_code == 400


def test_workspace_crud_and_settings(client):
    ws = client.post("/api/workspaces", json={"name": "Team Chennai"}).json()
    assert ws["role"] == "owner"
    assert ws["summary_language"] == "both"

    updated = client.patch(
        f"/api/workspaces/{ws['id']}",
        json={"summary_language": "ta", "custom_vocabulary": ["Neu AI", "Karthik", " "]},
    ).json()
    assert updated["summary_language"] == "ta"
    assert updated["custom_vocabulary"] == ["Neu AI", "Karthik"]

    resp = client.patch(f"/api/workspaces/{ws['id']}", json={"summary_language": "de"})
    assert resp.status_code == 400


def test_meetings_are_workspace_scoped(client, tmp_path):
    ws = client.post("/api/workspaces", json={"name": "Scoped"}).json()
    meeting = _upload(client, tmp_path, title="Scoped meeting", workspace_id=ws["id"])

    in_ws = client.get("/api/meetings", params={"workspace_id": ws["id"]}).json()
    assert any(m["id"] == meeting["id"] for m in in_ws)

    default_list = client.get("/api/meetings").json()  # default workspace
    assert not any(m["id"] == meeting["id"] for m in default_list)


def test_invite_flow(client):
    ws = client.post("/api/workspaces", json={"name": "Inviting"}).json()
    invite = client.post(
        f"/api/workspaces/{ws['id']}/invites",
        json={"email": "colleague@example.com", "role": "member"},
    ).json()
    assert invite["token"]

    pending = client.get(f"/api/workspaces/{ws['id']}/invites").json()
    assert len(pending) == 1

    # Wrong-email acceptance rejected (dev user is dev@localhost)
    resp = client.post(f"/api/invites/{invite['token']}/accept")
    assert resp.status_code == 403

    # Invite matching the dev user's email is accepted and grants membership
    ok_invite = client.post(
        f"/api/workspaces/{ws['id']}/invites",
        json={"email": "dev@localhost", "role": "member"},
    ).json()
    accepted = client.post(f"/api/invites/{ok_invite['token']}/accept")
    assert accepted.status_code == 200

    # Owner-role invites are rejected
    resp = client.post(
        f"/api/workspaces/{ws['id']}/invites", json={"email": "x@example.com", "role": "owner"}
    )
    assert resp.status_code == 400


def test_share_link_flow(client, tmp_path):
    meeting = _upload(client, tmp_path, title="Shareable")
    detail = _wait_completed(client, meeting["id"])

    token = client.post(f"/api/meetings/{meeting['id']}/share").json()["share_token"]
    assert token

    # Public endpoint works without any session
    shared = client.get(f"/api/shared/{token}")
    assert shared.status_code == 200
    assert shared.json()["title"] == "Shareable"
    assert len(shared.json()["segments"]) == len(detail["segments"])

    # Revoking kills the link
    client.delete(f"/api/meetings/{meeting['id']}/share")
    assert client.get(f"/api/shared/{token}").status_code == 404


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg needed for real audio")
def test_audio_streaming_with_range(client, tmp_path):
    meeting = _upload(client, tmp_path, title="Audio test")
    _wait_completed(client, meeting["id"])

    full = client.get(f"/api/meetings/{meeting['id']}/audio")
    assert full.status_code == 200
    assert full.headers["content-type"].startswith("audio/")

    partial = client.get(
        f"/api/meetings/{meeting['id']}/audio", headers={"Range": "bytes=0-99"}
    )
    assert partial.status_code == 206
    assert len(partial.content) == 100

    # Shared audio endpoint
    token = client.post(f"/api/meetings/{meeting['id']}/share").json()["share_token"]
    shared_audio = client.get(f"/api/shared/{token}/audio")
    assert shared_audio.status_code == 200


def test_last_owner_protected(client):
    ws = client.post("/api/workspaces", json={"name": "Solo"}).json()
    members = client.get(f"/api/workspaces/{ws['id']}/members").json()
    me = members[0]

    resp = client.patch(
        f"/api/workspaces/{ws['id']}/members/{me['id']}", json={"role": "viewer"}
    )
    assert resp.status_code == 400  # can't demote the only owner
