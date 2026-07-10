"""Action-item tracker: aggregate every action item across a workspace's
meetings into one list, and let the user tick them off.

Action items live inside each meeting's Summary (a JSON list of
{task, owner, due}); we address each one by (meeting_id, index) and store a
`done` flag right on the item, so no extra table or migration is needed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Meeting, User, WorkspaceMember
from ..schemas import TaskItem, TaskToggle
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _user_workspace_ids(db: Session, user: User, workspace_id: str | None) -> list[str]:
    ids = [
        m.workspace_id
        for m in db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()
    ]
    if workspace_id:
        if workspace_id not in ids:
            raise HTTPException(403, "Not a member of that workspace")
        return [workspace_id]
    return ids


@router.get("", response_model=list[TaskItem])
def list_tasks(
    workspace_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_ids = _user_workspace_ids(db, user, workspace_id)
    if not workspace_ids:
        return []

    meetings = (
        db.query(Meeting)
        .filter(Meeting.workspace_id.in_(workspace_ids), Meeting.status == "completed")
        .order_by(Meeting.created_at.desc())
        .all()
    )

    tasks: list[TaskItem] = []
    for meeting in meetings:
        if not meeting.summary or not meeting.summary.action_items:
            continue
        for i, item in enumerate(meeting.summary.action_items):
            if not isinstance(item, dict):
                continue
            task_text = str(item.get("task") or "").strip()
            if not task_text:
                continue
            tasks.append(
                TaskItem(
                    meeting_id=meeting.id,
                    meeting_title=meeting.title,
                    index=i,
                    task=task_text,
                    owner=(item.get("owner") or None),
                    due=(item.get("due") or None),
                    done=bool(item.get("done", False)),
                    created_at=meeting.created_at,
                )
            )
    return tasks


@router.patch("/{meeting_id}/{index}", response_model=TaskItem)
def toggle_task(
    meeting_id: str,
    index: int,
    body: TaskToggle,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_ids = _user_workspace_ids(db, user, None)
    meeting = db.get(Meeting, meeting_id)
    if meeting is None or meeting.workspace_id not in workspace_ids:
        raise HTTPException(404, "Meeting not found")
    if not meeting.summary or not meeting.summary.action_items:
        raise HTTPException(404, "No action items for this meeting")
    items = list(meeting.summary.action_items)
    if index < 0 or index >= len(items) or not isinstance(items[index], dict):
        raise HTTPException(404, "Action item not found")

    items[index] = {**items[index], "done": body.done}
    meeting.summary.action_items = items  # reassign so the JSON column is marked dirty
    db.commit()

    item = items[index]
    return TaskItem(
        meeting_id=meeting.id,
        meeting_title=meeting.title,
        index=index,
        task=str(item.get("task") or ""),
        owner=(item.get("owner") or None),
        due=(item.get("due") or None),
        done=bool(item.get("done", False)),
        created_at=meeting.created_at,
    )
