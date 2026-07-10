"""Meeting processing pipeline (executed by the job worker):

    audio -> normalize (ffmpeg) -> transcribe (chunked, with progress)
          -> diarize (optional) -> tag Tamil/English/Tanglish per segment
          -> Claude bilingual summary -> completed

Raises on failure so the job queue can retry; the queue marks the meeting
failed once attempts are exhausted.
"""

import logging
from pathlib import Path

from ..database import SessionLocal
from ..models import Meeting, Summary, TranscriptSegment
from .audio import normalize_audio
from .diarization import apply_diarization, assign_speakers_from_turns, diarization_enabled
from .language import classify_segments
from .stt import get_stt_provider
from .summarizer import summarize_meeting

logger = logging.getLogger("neu.pipeline")


def _load_bot_speaker_turns(meeting_id: str):
    """Return (start, end, speaker) tuples from the meeting's bot timeline, if any."""
    from ..models import Meeting

    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting and meeting.bot and meeting.bot.speaker_timeline:
            return [
                (t["start"], t["end"], t["speaker"]) for t in meeting.bot.speaker_timeline
            ]
        return []
    finally:
        db.close()


def _set_progress(meeting_id: str, progress: int, stage: str | None, status: str | None = None):
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return
        meeting.progress = progress
        meeting.stage = stage
        if status:
            meeting.status = status
        db.commit()
    finally:
        db.close()


async def process_meeting_job(meeting_id: str) -> None:
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return
        audio_path = meeting.audio_path
        # A retry may run after a partial earlier attempt — clear old output.
        for seg in list(meeting.segments):
            db.delete(seg)
        if meeting.summary:
            db.delete(meeting.summary)
        meeting.error = None
        db.commit()
    finally:
        db.close()

    # 1. Normalize audio (also validates the file is decodable)
    _set_progress(meeting_id, 5, "Preparing audio", status="transcribing")
    wav_path, duration = await normalize_audio(audio_path)

    # 2. Transcribe (provider handles chunking; progress 10 -> 70)
    def on_stt_progress(fraction: float) -> None:
        _set_progress(meeting_id, 10 + int(fraction * 60), "Transcribing")

    _set_progress(meeting_id, 10, "Transcribing")
    stt = get_stt_provider()
    result = await stt.transcribe(wav_path, on_progress=on_stt_progress)
    if duration and not result.duration_seconds:
        result.duration_seconds = duration

    # 3. Speaker labels. Prefer the meeting-bot's participant timeline (real
    #    names); otherwise fall back to optional pyannote diarization.
    if not any(s.speaker for s in result.segments):
        bot_turns = _load_bot_speaker_turns(meeting_id)
        if bot_turns:
            _set_progress(meeting_id, 72, "Labelling speakers")
            assign_speakers_from_turns(result.segments, bot_turns, relabel=False)
        elif diarization_enabled():
            _set_progress(meeting_id, 72, "Identifying speakers")
            try:
                await apply_diarization(wav_path, result.segments)
            except Exception:
                logger.exception("Diarization failed for %s — continuing without speakers", meeting_id)

    # The normalized WAV has served its purpose (transcription + diarization).
    # It's the largest working file (~1 MB per 15s of audio) and is fully
    # regenerable from the original on a re-run, so delete it now rather than
    # letting it accumulate on disk.
    if wav_path != audio_path:
        Path(wav_path).unlink(missing_ok=True)

    # 4. Language tagging (heuristic + optional LLM fallback for ambiguous spans)
    _set_progress(meeting_id, 78, "Tagging languages")
    languages, dominant, breakdown = await classify_segments([s.text for s in result.segments])

    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return
        for seg, lang in zip(result.segments, languages):
            db.add(
                TranscriptSegment(
                    meeting_id=meeting.id,
                    start=seg.start,
                    end=seg.end,
                    speaker=seg.speaker,
                    text=seg.text,
                    language=lang,
                )
            )
        meeting.language = dominant
        meeting.duration_seconds = result.duration_seconds or duration or None
        meeting.status = "summarizing"
        meeting.progress = 85
        meeting.stage = "Writing summary"
        db.commit()

        # 5. Summarize with Claude (respecting workspace preferences). A summary
        # failure (e.g. no API credits, rate limit) must NOT discard the
        # transcript — that's the expensive part and it already succeeded. Mark
        # the meeting completed and let the user re-summarize once resolved.
        db.refresh(meeting)
        workspace = meeting.workspace
        try:
            summary_data = await summarize_meeting(
                meeting.segments,
                summary_language=workspace.summary_language if workspace else "both",
                vocabulary=workspace.custom_vocabulary if workspace else None,
            )
            db.add(
                Summary(
                    meeting_id=meeting.id,
                    overview_en=summary_data.get("overview_en"),
                    overview_ta=summary_data.get("overview_ta"),
                    key_points=summary_data.get("key_points"),
                    action_items=summary_data.get("action_items"),
                    decisions=summary_data.get("decisions"),
                    topics=summary_data.get("topics"),
                    sentiment=summary_data.get("sentiment"),
                    language_breakdown=breakdown,
                )
            )
            meeting.error = None
        except Exception as exc:
            logger.warning("Summarization failed for %s (transcript kept): %s", meeting_id, exc)
            meeting.error = (
                f"Transcript is ready, but the AI summary couldn't be generated: {exc}. "
                "Resolve the issue, then click Re-summarize."
            )[:1500]
        meeting.status = "completed"
        meeting.progress = 100
        meeting.stage = None
        db.commit()
    finally:
        db.close()

    # Populate the Tasks board from this meeting's action items.
    from .task_sync import sync_meeting_tasks

    sync_meeting_tasks(meeting_id)

    # Email the recap to the meeting creator (no-op in dev / when SMTP unset).
    from .email_recap import send_recap

    send_recap(meeting_id)


async def summarize_meeting_job(meeting_id: str) -> None:
    """Regenerate only the summary from the current (possibly edited) transcript."""
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None or not meeting.segments:
            return
        meeting.status = "summarizing"
        meeting.progress = 85
        meeting.stage = "Writing summary"
        meeting.error = None
        db.commit()
        db.refresh(meeting)

        workspace = meeting.workspace
        try:
            summary_data = await summarize_meeting(
                meeting.segments,
                summary_language=workspace.summary_language if workspace else "both",
                vocabulary=workspace.custom_vocabulary if workspace else None,
            )
            languages = [s.language for s in meeting.segments if s.language]
            from .language import language_breakdown as breakdown_fn

            if meeting.summary:
                db.delete(meeting.summary)
                db.flush()
            db.add(
                Summary(
                    meeting_id=meeting.id,
                    overview_en=summary_data.get("overview_en"),
                    overview_ta=summary_data.get("overview_ta"),
                    key_points=summary_data.get("key_points"),
                    action_items=summary_data.get("action_items"),
                    decisions=summary_data.get("decisions"),
                    topics=summary_data.get("topics"),
                    sentiment=summary_data.get("sentiment"),
                    language_breakdown=breakdown_fn(languages),
                )
            )
            meeting.error = None
        except Exception as exc:
            logger.warning("Re-summarization failed for %s (transcript kept): %s", meeting_id, exc)
            meeting.error = (
                f"Transcript is ready, but the AI summary couldn't be generated: {exc}. "
                "Resolve the issue, then click Re-summarize."
            )[:1500]
        meeting.status = "completed"
        meeting.progress = 100
        meeting.stage = None
        db.commit()
    finally:
        db.close()

    # Sync any newly-surfaced action items onto the Tasks board.
    from .task_sync import sync_meeting_tasks

    sync_meeting_tasks(meeting_id)
