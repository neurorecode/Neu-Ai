"""Orchestrates the meeting-bot lifecycle:

  dispatch_bot()      -> create a Meeting + MeetingBot and send the bot to the call
  handle_bot_update() -> on status change; when 'done', download the recording,
                         store the speaker timeline, and enqueue the pipeline

Both the webhook and the poll-fallback funnel through handle_bot_update, so the
"recording ready -> transcribe" transition happens exactly once.
"""

import logging

from ..config import settings
from ..database import SessionLocal
from ..models import Meeting, MeetingBot
from .bots import get_bot_provider
from .bots.download import download_recording
from .jobs import enqueue

logger = logging.getLogger("neu.bot_service")


def webhook_url() -> str | None:
    if settings.bot_provider.lower() != "recall":
        return None
    return f"{settings.backend_url.rstrip('/')}/api/bots/webhook/{settings.webhook_secret}"


async def dispatch_bot(meeting_id: str, meeting_url: str) -> None:
    """Send a bot to the meeting and record its id/status."""
    provider = get_bot_provider()
    handle = await provider.create_bot(meeting_url, settings.bot_name, webhook_url())

    db = SessionLocal()
    try:
        bot = db.query(MeetingBot).filter(MeetingBot.meeting_id == meeting_id).first()
        if bot is None:
            return
        bot.provider_bot_id = handle.provider_bot_id
        bot.status = handle.status
        meeting = db.get(Meeting, meeting_id)
        if meeting:
            meeting.stage = _stage_for(handle.status)
        db.commit()
    finally:
        db.close()

    # Mock provider reports 'done' immediately — process without waiting on a webhook.
    if handle.status == "done":
        await handle_bot_update(meeting_id=meeting_id)


def _stage_for(status: str) -> str:
    return {
        "joining": "Bot joining the call",
        "recording": "Bot recording the meeting",
        "done": "Fetching recording",
        "failed": "Bot failed to join",
        "left": "Call ended",
    }.get(status, "Waiting for the call")


async def handle_bot_update(
    *, meeting_id: str | None = None, provider_bot_id: str | None = None, status: str | None = None
) -> None:
    """Advance a bot. Idempotent: only the first transition to 'done' triggers
    the download + pipeline enqueue."""
    db = SessionLocal()
    try:
        query = db.query(MeetingBot)
        if meeting_id:
            bot = query.filter(MeetingBot.meeting_id == meeting_id).first()
        else:
            bot = query.filter(MeetingBot.provider_bot_id == provider_bot_id).first()
        if bot is None:
            return
        meeting_id = bot.meeting_id
        provider_bot_id = bot.provider_bot_id
        if status:
            bot.status = status
        meeting = db.get(Meeting, meeting_id)
        if meeting:
            meeting.stage = _stage_for(bot.status)
        current_status = bot.status
        # Idempotency: the recording is downloaded exactly once — guard on
        # whether we've already fetched audio for this (bot-sourced) meeting.
        needs_processing = current_status == "done" and (
            meeting is not None and meeting.audio_path is None
        )
        db.commit()
    finally:
        db.close()

    if current_status in ("failed", "left"):
        _mark_failed(meeting_id, f"Bot {current_status}")
        return
    if not needs_processing:
        return

    # First time reaching 'done' — fetch, download, enqueue.
    try:
        provider = get_bot_provider()
        recording = await provider.fetch_recording(provider_bot_id)
        audio_path = await download_recording(meeting_id, recording.audio_url, recording.audio_ext)

        db = SessionLocal()
        try:
            meeting = db.get(Meeting, meeting_id)
            bot = db.query(MeetingBot).filter(MeetingBot.meeting_id == meeting_id).first()
            if meeting is None:
                return
            meeting.audio_path = audio_path
            meeting.status = "uploaded"
            meeting.stage = "Queued"
            if bot and recording.speakers:
                bot.speaker_timeline = [
                    {"start": s.start, "end": s.end, "speaker": s.speaker} for s in recording.speakers
                ]
            enqueue(db, meeting_id, "process")
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Failed to fetch bot recording for %s", meeting_id)
        _mark_failed(meeting_id, f"Could not fetch recording: {exc}")


def _mark_failed(meeting_id: str, message: str) -> None:
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting and meeting.status not in ("completed",):
            meeting.status = "failed"
            meeting.error = message[:2000]
            meeting.stage = None
            db.commit()
    finally:
        db.close()
