import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Meeting, MeetingBot, User
from ..schemas import BotStatusOut, InviteBotRequest, MeetingOut
from ..services.auth import default_workspace_id, get_current_user, get_membership, require_role
from ..services.bot_service import dispatch_bot, handle_bot_update
from ..services.bots import bots_enabled

logger = logging.getLogger("neu.routers.bots")

router = APIRouter(prefix="/api/meetings", tags=["bots"])

# Recognized meeting-link shapes → a friendly platform name
PLATFORM_PATTERNS = [
    (re.compile(r"meet\.google\.com/", re.I), "Google Meet"),
    (re.compile(r"zoom\.us/j/|zoom\.us/w/|zoom\.us/my/", re.I), "Zoom"),
    (re.compile(r"teams\.microsoft\.com/|teams\.live\.com/", re.I), "Microsoft Teams"),
]


def _platform(url: str) -> str | None:
    for pattern, name in PLATFORM_PATTERNS:
        if pattern.search(url):
            return name
    return None


@router.post("/invite-bot", response_model=MeetingOut, status_code=201)
async def invite_bot(
    body: InviteBotRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send Neu's notetaker bot to a live Google Meet / Zoom / Teams call."""
    if not bots_enabled():
        raise HTTPException(
            400,
            "Meeting bot is not configured. Set BOT_PROVIDER=recall and RECALL_API_KEY "
            "(see DEPLOY.md) to let Neu auto-join calls.",
        )
    meeting_url = body.meeting_url.strip()
    platform = _platform(meeting_url)
    if not platform:
        raise HTTPException(400, "That doesn't look like a Google Meet, Zoom, or Teams link")

    workspace_id = body.workspace_id or default_workspace_id(db, user)
    member = get_membership(db, user, workspace_id)
    require_role(member, "owner", "member")

    meeting = Meeting(
        title=body.title.strip() if body.title else f"{platform} meeting",
        status="uploaded",
        stage="Bot joining the call",
        source="bot",
        workspace_id=workspace_id,
        created_by=user.id,
    )
    db.add(meeting)
    db.flush()
    db.add(MeetingBot(meeting_id=meeting.id, provider=settings.bot_provider, meeting_url=meeting_url))
    db.commit()

    background_tasks.add_task(dispatch_bot, meeting.id, meeting_url)
    return meeting


@router.get("/{meeting_id}/bot", response_model=BotStatusOut)
def get_bot(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if meeting.workspace_id:
        get_membership(db, user, meeting.workspace_id)
    if meeting.bot is None:
        raise HTTPException(404, "This meeting has no bot")
    return meeting.bot


# --- provider webhook (no user auth; guarded by the secret in the path) ------

webhook_router = APIRouter(prefix="/api/bots", tags=["bots"])


@webhook_router.post("/webhook/{secret}")
async def bot_webhook(secret: str, request: Request, background_tasks: BackgroundTasks):
    if secret != settings.webhook_secret:
        raise HTTPException(403, "Invalid webhook secret")
    payload = await request.json()

    # Recall payloads: {"event": "bot.status_change", "data": {"bot_id": ..,
    #                    "status": {"code": ".."}}} (shape tolerant)
    data = payload.get("data", payload)
    provider_bot_id = data.get("bot_id") or data.get("id")
    code = None
    status_obj = data.get("status")
    if isinstance(status_obj, dict):
        code = status_obj.get("code")
    code = code or data.get("code")

    from ..services.bots.recall import STATUS_MAP

    normalized = STATUS_MAP.get(code or "", None)
    if not provider_bot_id:
        return {"ok": True, "ignored": "no bot id"}

    background_tasks.add_task(
        handle_bot_update, provider_bot_id=provider_bot_id, status=normalized
    )
    return {"ok": True}
