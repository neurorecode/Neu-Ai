"""Google Calendar integration: list upcoming meetings and extract their
video-call links (Meet / Zoom / Teams) so Neu can join.

Uses the refresh token stored at sign-in to mint access tokens on demand.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings
from ..models import User

logger = logging.getLogger("neu.calendar")

TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

MEETING_LINK_PATTERNS = [
    re.compile(r"https://meet\.google\.com/[a-z\-]+", re.I),
    re.compile(r"https://[\w.]*zoom\.us/j/\d+(?:\?pwd=[\w.\-]+)?", re.I),
    re.compile(r"https://teams\.microsoft\.com/l/meetup-join/[^\s\"'<>]+", re.I),
]


class CalendarNotConnected(Exception):
    pass


async def _access_token(db, user: User) -> str:
    """Return a valid access token, refreshing via the stored refresh token."""
    now = datetime.now(timezone.utc)
    if user.google_access_token and user.google_token_expiry:
        expiry = user.google_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry > now:
            return user.google_access_token

    if not user.google_refresh_token:
        raise CalendarNotConnected("Calendar not connected — sign in again to grant access")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": user.google_refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        logger.warning("Token refresh failed for %s: %s", user.email, resp.text[:200])
        raise CalendarNotConnected("Calendar access expired — sign in again")
    data = resp.json()
    user.google_access_token = data["access_token"]
    user.google_token_expiry = now + timedelta(seconds=int(data.get("expires_in", 3600)) - 60)
    db.commit()
    return user.google_access_token


def extract_meeting_link(event: dict) -> str | None:
    # Google Meet is usually in hangoutLink or conferenceData
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    conf = event.get("conferenceData", {})
    for ep in conf.get("entryPoints", []):
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            return ep["uri"]
    # Zoom/Teams links often live in location or description
    for field in (event.get("location", ""), event.get("description", "")):
        for pattern in MEETING_LINK_PATTERNS:
            m = pattern.search(field or "")
            if m:
                return m.group(0)
    return None


async def list_upcoming(db, user: User, hours: int = 24) -> list[dict]:
    """Return upcoming calendar events with a detected meeting link."""
    token = await _access_token(db, user)
    now = datetime.now(timezone.utc)
    params = {
        "timeMin": now.isoformat(),
        "timeMax": (now + timedelta(hours=hours)).isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "50",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            EVENTS_URL, headers={"Authorization": f"Bearer {token}"}, params=params
        )
    if resp.status_code != 200:
        raise CalendarNotConnected(f"Calendar request failed: {resp.text[:200]}")

    events = []
    for item in resp.json().get("items", []):
        link = extract_meeting_link(item)
        start = item.get("start", {})
        events.append(
            {
                "id": item.get("id"),
                "title": item.get("summary", "(no title)"),
                "start": start.get("dateTime") or start.get("date"),
                "meeting_url": link,
                "attendees": len(item.get("attendees", []) or []),
            }
        )
    return events
