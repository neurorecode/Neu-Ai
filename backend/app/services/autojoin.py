"""Background auto-join poller.

Every few minutes, for each user who enabled auto-join, look at their calendar
for meetings starting soon that have a video link, and dispatch Neu's bot to
any not already joined. Inert unless both Google auth and a bot provider are
configured, so it does nothing in dev/tests.
"""

import asyncio
import logging
from datetime import datetime, timezone

from ..config import settings
from ..database import SessionLocal
from ..models import Meeting, MeetingBot, User
from ..services import calendar as cal
from ..services.auth import auth_enabled, default_workspace_id
from ..services.bot_service import dispatch_bot
from ..services.bots import bots_enabled

logger = logging.getLogger("neu.autojoin")

POLL_INTERVAL = 120.0  # seconds
# Join when a meeting starts within this many minutes.
JOIN_WINDOW_MINUTES = 5


def _parse_start(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def _poll_once() -> int:
    """Dispatch bots for imminent meetings. Returns how many were dispatched."""
    db = SessionLocal()
    dispatched = 0
    try:
        users = db.query(User).filter(User.auto_join == "video", User.google_refresh_token.isnot(None)).all()
        now = datetime.now(timezone.utc)
        for user in users:
            try:
                events = await cal.list_upcoming(db, user, hours=1)
            except cal.CalendarNotConnected:
                continue
            for ev in events:
                if not ev["meeting_url"] or not ev["id"]:
                    continue
                start = _parse_start(ev["start"])
                if start is None:
                    continue
                minutes_until = (start - now).total_seconds() / 60
                if minutes_until > JOIN_WINDOW_MINUTES or minutes_until < -30:
                    continue
                # Dedup: already joined this calendar event?
                exists = db.query(Meeting).filter(Meeting.calendar_event_id == ev["id"]).first()
                if exists:
                    continue

                meeting = Meeting(
                    title=ev["title"],
                    status="uploaded",
                    stage="Bot joining the call",
                    source="bot",
                    calendar_event_id=ev["id"],
                    workspace_id=default_workspace_id(db, user),
                    created_by=user.id,
                )
                db.add(meeting)
                db.flush()
                db.add(MeetingBot(meeting_id=meeting.id, provider=settings.bot_provider, meeting_url=ev["meeting_url"]))
                db.commit()
                await dispatch_bot(meeting.id, ev["meeting_url"])
                dispatched += 1
                logger.info("Auto-joined '%s' for %s", ev["title"], user.email)
        return dispatched
    finally:
        db.close()


async def autojoin_loop(stop_event: asyncio.Event) -> None:
    if not (auth_enabled() and bots_enabled()):
        logger.info("Auto-join poller inactive (needs Google auth + bot provider)")
        return
    logger.info("Auto-join poller started")
    while not stop_event.is_set():
        try:
            await _poll_once()
        except Exception:
            logger.exception("Auto-join poll failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass
    logger.info("Auto-join poller stopped")
