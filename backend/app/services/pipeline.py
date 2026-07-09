"""Meeting processing pipeline (executed by the job worker):

    audio -> normalize (ffmpeg) -> transcribe (chunked, with progress)
          -> diarize (optional) -> tag Tamil/English/Tanglish per segment
          -> Claude bilingual summary -> completed

Raises on failure so the job queue can retry; the queue marks the meeting
failed once attempts are exhausted.
"""

import logging

from ..database import SessionLocal
from ..models import Meeting, Summary, TranscriptSegment
from .audio import normalize_audio
from .diarization import apply_diarization, diarization_enabled
from .language import classify_segments
from .stt import get_stt_provider
from .summarizer import summarize_meeting

logger = logging.getLogger("neu.pipeline")


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

    # 3. Optional speaker diarization for providers that don't label speakers
    if diarization_enabled() and not any(s.speaker for s in result.segments):
        _set_progress(meeting_id, 72, "Identifying speakers")
        try:
            await apply_diarization(wav_path, result.segments)
        except Exception:
            logger.exception("Diarization failed for %s — continuing without speakers", meeting_id)

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

        # 5. Summarize with Claude
        db.refresh(meeting)
        summary_data = await summarize_meeting(meeting.segments)
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
        meeting.status = "completed"
        meeting.progress = 100
        meeting.stage = None
        db.commit()
    finally:
        db.close()


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

        summary_data = await summarize_meeting(meeting.segments)
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
        meeting.status = "completed"
        meeting.progress = 100
        meeting.stage = None
        db.commit()
    finally:
        db.close()
