"""Keep the Tasks board in sync with meeting action items.

Each action item in a meeting's summary becomes a Task (source='meeting').
Sync is additive and idempotent: it only creates tasks for action items that
don't already have one (matched by meeting + title), so a user's status
changes, edits, and manual tasks are never clobbered.
"""

import logging

from ..database import SessionLocal
from ..models import Meeting, Task

logger = logging.getLogger("neu.task_sync")


def _sync(db, meeting: Meeting) -> int:
    if not meeting.summary or not meeting.summary.action_items:
        return 0
    existing = {
        t.title
        for t in db.query(Task.title).filter(Task.meeting_id == meeting.id).all()
    }
    created = 0
    for item in meeting.summary.action_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("task") or "").strip()
        if not title or title in existing:
            continue
        db.add(
            Task(
                workspace_id=meeting.workspace_id,
                created_by=meeting.created_by,
                meeting_id=meeting.id,
                title=title,
                owner=(str(item.get("owner")).strip() or None) if item.get("owner") else None,
                due=(str(item.get("due")).strip() or None) if item.get("due") else None,
                status="done" if item.get("done") else "todo",
                source="meeting",
            )
        )
        existing.add(title)
        created += 1
    return created


def sync_meeting_tasks(meeting_id: str) -> None:
    """Create tasks for a single meeting's action items (idempotent)."""
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return
        if _sync(db, meeting):
            db.commit()
    finally:
        db.close()


def backfill_tasks() -> None:
    """One-time (idempotent) sweep so existing meetings populate the board."""
    db = SessionLocal()
    try:
        meetings = db.query(Meeting).filter(Meeting.status == "completed").all()
        total = 0
        for meeting in meetings:
            total += _sync(db, meeting)
        if total:
            db.commit()
            logger.info("Task backfill created %d tasks from existing meetings", total)
    except Exception:
        logger.exception("Task backfill failed")
    finally:
        db.close()
