import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Invite, User, Workspace, WorkspaceMember
from ..schemas import (
    InviteCreate,
    InviteOut,
    MemberOut,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from ..services.auth import get_current_user, get_membership, require_role

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

VALID_ROLES = {"owner", "member", "viewer"}
SUMMARY_LANGUAGES = {"en", "ta", "both"}


def _with_role(workspace: Workspace, role: str) -> WorkspaceOut:
    out = WorkspaceOut.model_validate(workspace)
    out.role = role
    return out


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    members = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at)
        .all()
    )
    return [_with_role(m.workspace, m.role) for m in members]


@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Workspace name cannot be empty")
    workspace = Workspace(name=name)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    db.commit()
    return _with_role(workspace, "owner")


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = get_membership(db, user, workspace_id)
    require_role(member, "owner")
    workspace = member.workspace

    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "Workspace name cannot be empty")
        workspace.name = body.name.strip()
    if body.summary_language is not None:
        if body.summary_language not in SUMMARY_LANGUAGES:
            raise HTTPException(400, f"summary_language must be one of {sorted(SUMMARY_LANGUAGES)}")
        workspace.summary_language = body.summary_language
    if body.custom_vocabulary is not None:
        workspace.custom_vocabulary = [w.strip() for w in body.custom_vocabulary if w.strip()][:200]
    db.commit()
    return _with_role(workspace, member.role)


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(db, user, workspace_id)
    return (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at)
        .all()
    )


@router.patch("/{workspace_id}/members/{member_id}", response_model=MemberOut)
def change_member_role(
    workspace_id: str,
    member_id: str,
    body: MemberRoleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = get_membership(db, user, workspace_id)
    require_role(me, "owner")
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(VALID_ROLES)}")

    target = db.get(WorkspaceMember, member_id)
    if target is None or target.workspace_id != workspace_id:
        raise HTTPException(404, "Member not found")
    if target.user_id == user.id and body.role != "owner":
        owners = [
            m for m in target.workspace.members if m.role == "owner" and m.id != target.id
        ]
        if not owners:
            raise HTTPException(400, "A workspace needs at least one owner")
    target.role = body.role
    db.commit()
    return target


@router.delete("/{workspace_id}/members/{member_id}", status_code=204)
def remove_member(
    workspace_id: str,
    member_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = get_membership(db, user, workspace_id)
    target = db.get(WorkspaceMember, member_id)
    if target is None or target.workspace_id != workspace_id:
        raise HTTPException(404, "Member not found")
    # Owners can remove anyone; anyone can remove themselves (leave)
    if target.user_id != user.id:
        require_role(me, "owner")
    if target.role == "owner":
        owners = [m for m in target.workspace.members if m.role == "owner" and m.id != target.id]
        if not owners:
            raise HTTPException(400, "A workspace needs at least one owner")
    db.delete(target)
    db.commit()


@router.post("/{workspace_id}/invites", response_model=InviteOut, status_code=201)
def create_invite(
    workspace_id: str,
    body: InviteCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = get_membership(db, user, workspace_id)
    require_role(me, "owner", "member")
    if body.role not in VALID_ROLES or body.role == "owner":
        raise HTTPException(400, "Invite role must be 'member' or 'viewer'")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Invalid email")

    invite = Invite(
        workspace_id=workspace_id,
        email=email,
        role=body.role,
        token=uuid.uuid4().hex,
        created_by=user.id,
    )
    db.add(invite)
    db.commit()
    return invite


@router.get("/{workspace_id}/invites", response_model=list[InviteOut])
def list_invites(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(db, user, workspace_id)
    return (
        db.query(Invite)
        .filter(Invite.workspace_id == workspace_id, Invite.accepted_at.is_(None))
        .order_by(Invite.created_at.desc())
        .all()
    )


@router.delete("/{workspace_id}/invites/{invite_id}", status_code=204)
def revoke_invite(
    workspace_id: str,
    invite_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = get_membership(db, user, workspace_id)
    require_role(me, "owner", "member")
    invite = db.get(Invite, invite_id)
    if invite is None or invite.workspace_id != workspace_id:
        raise HTTPException(404, "Invite not found")
    db.delete(invite)
    db.commit()


# --- invite acceptance lives outside the workspace prefix -------------------

accept_router = APIRouter(prefix="/api/invites", tags=["workspaces"])


@accept_router.post("/{token}/accept", response_model=WorkspaceOut)
def accept_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    invite = db.query(Invite).filter(Invite.token == token).first()
    if invite is None or invite.accepted_at is not None:
        raise HTTPException(404, "Invite not found or already used")
    if invite.email.lower() != user.email.lower():
        raise HTTPException(403, f"This invite was issued for {invite.email}")

    existing = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == invite.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    if existing is None:
        db.add(
            WorkspaceMember(
                workspace_id=invite.workspace_id, user_id=user.id, role=invite.role
            )
        )
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    workspace = db.get(Workspace, invite.workspace_id)
    return _with_role(workspace, existing.role if existing else invite.role)
