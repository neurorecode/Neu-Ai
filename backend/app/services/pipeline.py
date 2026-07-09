"""Background processing pipeline:

    audio file -> transcribe -> tag Tamil/English/Tanglish per segment
               -> Claude summary (bilingual) -> completed
"""

import logging

from ..database import SessionLocal
from ..models import Meeting, Summary, TranscriptSegment
from .language import detect_language, dominant_language, language_breakdown
from .stt import get_stt_provider
from .summarizer import summarize_meeting

logger = logging.getLogger("neu.pipeline")


async def process_meeting(meeting_id: str) -> None:
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None:
            return

        # 1. Transcribe
        meeting.status = "transcribing"
        db.commit()

        stt = get_stt_provider()
        result = await stt.transcribe(meeting.audio_path)

        # 2. Language-tag and store segments
        languages: list[str] = []
        for seg in result.segments:
            lang = detect_language(seg.text)
            languages.append(lang)
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
        meeting.language = dominant_language(languages)
        meeting.duration_seconds = result.duration_seconds
        meeting.status = "summarizing"
        db.commit()

        # 3. Summarize with Claude
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
                language_breakdown=language_breakdown(languages),
            )
        )
        meeting.status = "completed"
        db.commit()
    except Exception as exc:  # surface the failure on the meeting record
        logger.exception("Pipeline failed for meeting %s", meeting_id)
        db.rollback()
        meeting = db.get(Meeting, meeting_id)
        if meeting is not None:
            meeting.status = "failed"
            meeting.error = str(exc)[:2000]
            db.commit()
    finally:
        db.close()
