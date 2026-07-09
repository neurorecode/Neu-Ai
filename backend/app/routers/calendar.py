from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services import calendar as cal
from ..services.auth import auth_enabled, get_current_user
from ..services.bots import bots_enabled

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class CalendarEvent(BaseModel):
    id: str | None
    title: str
    start: str | None
    meeting_url: str | None
    attendees: int


class CalendarStatus(BaseModel):
    connected: bool
    auto_join: str
    bots_enabled: bool


class AutoJoinUpdate(BaseModel):
    auto_join: str  # none | video


@router.get("/status", response_model=CalendarStatus)
def status(user: User = Depends(get_current_user)):
    return CalendarStatus(
        connected=bool(user.google_refresh_token) or not auth_enabled(),
        auto_join=user.auto_join,
        bots_enabled=bots_enabled(),
    )


@router.get("/events", response_model=list[CalendarEvent])
async def events(
    hours: int = 24,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not auth_enabled():
        raise HTTPException(400, "Calendar requires Google sign-in (dev mode is active)")
    try:
        return await cal.list_upcoming(db, user, hours=min(hours, 168))
    except cal.CalendarNotConnected as e:
        raise HTTPException(400, str(e))


@router.put("/auto-join", response_model=CalendarStatus)
def set_auto_join(
    body: AutoJoinUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.auto_join not in ("none", "video"):
        raise HTTPException(400, "auto_join must be 'none' or 'video'")
    user.auto_join = body.auto_join
    db.commit()
    return CalendarStatus(
        connected=bool(user.google_refresh_token) or not auth_enabled(),
        auto_join=user.auto_join,
        bots_enabled=bots_enabled(),
    )
