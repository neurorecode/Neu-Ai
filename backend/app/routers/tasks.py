"""Kanban task board: meeting-derived + manual tasks, with CRUD.

Tasks live in their own table (see models.Task). Meeting action items are
synced in as tasks (services.task_sync); users can also create manual tasks,
move them between columns (todo/doing/done), edit, and delete.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task, User, WorkspaceMember
from ..schemas import TaskCreate, TaskOut, TaskUpdate
from ..services.auth import default_workspace_id, get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

STATUSES = {"todo", "doing", "done"}


def _workspace_ids(db: Session, user: User, workspace_id: str | None) -> list[str]:
    ids = [
        m.workspace_id
        for m in db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()
    ]
    if workspace_id:
        if workspace_id not in ids:
            raise HTTPException(403, "Not a member of that workspace")
        return [workspace_id]
    return ids


def _get_owned(db: Session, user: User, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.workspace_id not in _workspace_ids(db, user, None):
        raise HTTPException(404, "Task not found")
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    workspace_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_ids = _workspace_ids(db, user, workspace_id)
    if not workspace_ids:
        return []
    return (
        db.query(Task)
        .filter(Task.workspace_id.in_(workspace_ids))
        .order_by(Task.updated_at.desc())
        .all()
    )


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "Task title is empty")
    status = body.status if body.status in STATUSES else "todo"
    workspace_id = body.workspace_id or default_workspace_id(db, user)
    if workspace_id not in _workspace_ids(db, user, None):
        raise HTTPException(403, "Not a member of that workspace")

    task = Task(
        workspace_id=workspace_id,
        created_by=user.id,
        title=title,
        owner=(body.owner or None),
        due=(body.due or None),
        status=status,
        source="manual",
        done_at=datetime.now(timezone.utc) if status == "done" else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    body: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned(db, user, task_id)
    if body.title is not None:
        t = body.title.strip()
        if not t:
            raise HTTPException(400, "Task title is empty")
        task.title = t
    if body.owner is not None:
        task.owner = body.owner or None
    if body.due is not None:
        task.due = body.due or None
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(400, "Invalid status")
        # Stamp/clear done_at as it enters/leaves the Done column.
        if body.status == "done" and task.status != "done":
            task.done_at = datetime.now(timezone.utc)
        elif body.status != "done":
            task.done_at = None
        task.status = body.status
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned(db, user, task_id)
    db.delete(task)
    db.commit()
