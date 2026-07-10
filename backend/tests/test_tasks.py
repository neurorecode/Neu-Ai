"""Action-item tracker: aggregate across meetings + toggle done."""

from app.database import SessionLocal
from app.models import Meeting, Summary, Workspace


def _seed(title, action_items):
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


def test_tasks_aggregate_and_toggle(client):
    # Trigger dev workspace/user creation, then seed action items.
    client.get("/api/meetings")
    mid = _seed(
        "Sales sync",
        [
            {"task": "Prepare objection doc", "owner": "Karthik", "due": "Fri"},
            {"task": "Follow up with Sathish", "owner": "Sreepriya", "due": ""},
        ],
    )

    tasks = client.get("/api/tasks").json()
    mine = [t for t in tasks if t["meeting_id"] == mid]
    assert len(mine) == 2
    assert {t["task"] for t in mine} == {"Prepare objection doc", "Follow up with Sathish"}
    assert all(t["done"] is False for t in mine)
    assert mine[0]["meeting_title"] == "Sales sync"

    # Tick the first one done.
    resp = client.patch(f"/api/tasks/{mid}/0", json={"done": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["done"] is True

    # Persisted on re-fetch.
    tasks = client.get("/api/tasks").json()
    done = {t["index"]: t["done"] for t in tasks if t["meeting_id"] == mid}
    assert done[0] is True and done[1] is False


def test_toggle_bad_index_404(client):
    client.get("/api/meetings")
    mid = _seed("Solo", [{"task": "Only task"}])
    assert client.patch(f"/api/tasks/{mid}/9", json={"done": True}).status_code == 404
