"""Orchestrates the meeting-bot lifecycle:

  dispatch_bot()      -> create a Meeting + MeetingBot and send the bot to the call
  handle_bot_update() -> on status change; when 'done', download the recording,
                         store the speaker timeline, and enqueue the pipeline
  bot_poll_loop()     -> safety net: polls in-flight bots so completion doesn't
                         depend on the webhook being deliverable

Both the webhook and the poller funnel through handle_bot_update, so the
"recording ready -> transcribe" transition happens exactly once.
"""

import asyncio
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

    # First time reaching 'done' — fetch, download, enqueue. The download URL
    # can lag the 'done' status by a few seconds, so retry a handful of times.
    try:
        provider = get_bot_provider()
        recording = None
        for attempt in range(6):
            try:
                recording = await provider.fetch_recording(provider_bot_id)
                break
            except Exception as fetch_exc:
                if attempt == 5:
                    raise
                logger.info(
                    "Recording not ready for %s (attempt %d), retrying: %s",
                    meeting_id, attempt + 1, fetch_exc,
                )
                await asyncio.sleep(10)
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


async def poll_active_bots() -> None:
    """Check in-flight bots against the provider and advance any that finished.
    Runs regardless of webhook delivery, so a broken/unreachable webhook never
    leaves a bot stuck."""
    from .bots import bots_enabled, get_bot_provider

    if not bots_enabled():
        return

    db = SessionLocal()
    try:
        active_ids = [
            b.provider_bot_id
            for b in db.query(MeetingBot)
            .filter(
                MeetingBot.provider_bot_id.isnot(None),
                MeetingBot.status.in_(("joining", "recording")),
            )
            .all()
        ]
    finally:
        db.close()
    if not active_ids:
        return

    provider = get_bot_provider()
    for provider_bot_id in active_ids:
        try:
            st = await provider.get_status(provider_bot_id)
            await handle_bot_update(provider_bot_id=provider_bot_id, status=st.status)
        except Exception:
            logger.exception("Bot poll failed for %s", provider_bot_id)


async def bot_poll_loop(stop_event: asyncio.Event, interval: float = 30.0) -> None:
    from .bots import bots_enabled

    if not bots_enabled():
        logger.info("Bot status poller inactive (no bot provider configured)")
        return
    logger.info("Bot status poller started")
    while not stop_event.is_set():
        try:
            await poll_active_bots()
        except Exception:
            logger.exception("Bot poll loop error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    logger.info("Bot status poller stopped")
