"""Kanban tasks: meeting sync, manual CRUD, status moves, archive."""

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Meeting, Summary, Task, Workspace


def _seed_meeting(title, action_items):
    db = SessionLocal()
    try:
        ws = db.query(Workspace).first()
        m = Meeting(title=title, status="completed", workspace_id=ws.id if ws else None)
        db.add(m)
        db.flush()
        db.add(Summary(meeting_id=m.id, action_items=action_items))
        db.commit()
        return m.id
    finally:
        db.close()


def test_meeting_sync_creates_tasks(client):
    client.get("/api/meetings")  # ensure dev workspace exists
    from app.services.task_sync import sync_meeting_tasks

    mid = _seed_meeting(
        "Sales sync",
        [
            {"task": "Prepare objection doc", "owner": "Karthik", "due": "Fri"},
            {"task": "Follow up with Sathish", "owner": "Sreepriya"},
            {"task": "Already handled", "done": True},
        ],
    )
    sync_meeting_tasks(mid)

    tasks = client.get("/api/tasks").json()
    mine = [t for t in tasks if t["meeting_id"] == mid]
    assert len(mine) == 3
    by_title = {t["title"]: t for t in mine}
    assert by_title["Prepare objection doc"]["owner"] == "Karthik"
    assert by_title["Prepare objection doc"]["status"] == "todo"
    assert by_title["Already handled"]["status"] == "done"
    assert all(t["source"] == "meeting" for t in mine)

    # Idempotent: syncing again creates nothing new.
    sync_meeting_tasks(mid)
    again = [t for t in client.get("/api/tasks").json() if t["meeting_id"] == mid]
    assert len(again) == 3


def test_manual_task_crud_and_move(client):
    client.get("/api/meetings")
    created = client.post("/api/tasks", json={"title": "Call the vendor", "owner": "Me"})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["status"] == "todo"
    assert created.json()["source"] == "manual"

    # Move across columns
    moved = client.patch(f"/api/tasks/{tid}", json={"status": "doing"})
    assert moved.json()["status"] == "doing"
    done = client.patch(f"/api/tasks/{tid}", json={"status": "done"})
    assert done.json()["status"] == "done"
    assert done.json()["archived"] is False  # just completed, not archived yet

    # Edit
    edited = client.patch(f"/api/tasks/{tid}", json={"title": "Call vendor tomorrow", "due": "Tue"})
    assert edited.json()["title"] == "Call vendor tomorrow"
    assert edited.json()["due"] == "Tue"

    # Delete
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert tid not in {t["id"] for t in client.get("/api/tasks").json()}


def test_reject_empty_title(client):
    client.get("/api/meetings")
    assert client.post("/api/tasks", json={"title": "   "}).status_code == 400


def test_archived_after_30_days(client):
    client.get("/api/meetings")
    tid = client.post("/api/tasks", json={"title": "Old done task", "status": "done"}).json()["id"]
    # Backdate done_at beyond the archive window.
    db = SessionLocal()
    try:
        t = db.get(Task, tid)
        t.done_at = datetime.now(timezone.utc) - timedelta(days=40)
        db.commit()
    finally:
        db.close()
    got = {t["id"]: t for t in client.get("/api/tasks").json()}
    assert got[tid]["archived"] is True
