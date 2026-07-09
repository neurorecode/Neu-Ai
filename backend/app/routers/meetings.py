import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Meeting, TranscriptSegment
from ..schemas import (
    MeetingDetail,
    MeetingOut,
    SearchHit,
    SegmentOut,
    SegmentUpdate,
    SpeakerRename,
)
from ..services.jobs import enqueue
from ..services.language import detect_language

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"}


@router.get("", response_model=list[MeetingOut])
def list_meetings(db: Session = Depends(get_db)):
    return db.query(Meeting).order_by(Meeting.created_at.desc()).all()


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
    file: UploadFile = File(...),
    title: str = Form("Untitled meeting"),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "audio.webm").suffix.lower() or ".webm"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'")

    meeting = Meeting(title=title.strip() or "Untitled meeting", status="uploaded")
    db.add(meeting)
    db.commit()

    dest = Path(settings.upload_dir) / f"{meeting.id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    meeting.audio_path = str(dest)
    db.commit()

    enqueue(db, meeting.id, "process")
    return meeting


@router.get("/search", response_model=list[SearchHit])
def search(q: str, db: Session = Depends(get_db)):
    q = q.strip()
    if not q:
        return []
    pattern = f"%{q}%"

    hits: list[SearchHit] = []
    seg_rows = (
        db.query(TranscriptSegment, Meeting)
        .join(Meeting, TranscriptSegment.meeting_id == Meeting.id)
        .filter(TranscriptSegment.text.like(pattern))
        .limit(50)
        .all()
    )
    for seg, meeting in seg_rows:
        hits.append(
            SearchHit(
                meeting_id=meeting.id,
                meeting_title=meeting.title,
                segment_id=seg.id,
                snippet=seg.text,
                start=seg.start,
            )
        )

    title_rows = db.query(Meeting).filter(or_(Meeting.title.like(pattern))).limit(20).all()
    seen = {h.meeting_id for h in hits}
    for meeting in title_rows:
        if meeting.id not in seen:
            hits.append(
                SearchHit(
                    meeting_id=meeting.id,
                    meeting_title=meeting.title,
                    segment_id=None,
                    snippet=meeting.title,
                    start=None,
                )
            )
    return hits


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    return meeting


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if meeting.audio_path:
        base = Path(meeting.audio_path)
        base.unlink(missing_ok=True)
        base.with_suffix(".norm.wav").unlink(missing_ok=True)
    db.delete(meeting)
    db.commit()


@router.post("/{meeting_id}/reprocess", response_model=MeetingOut)
def reprocess(meeting_id: str, db: Session = Depends(get_db)):
    """Re-run the full pipeline (transcription + summary) from the original audio."""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if not meeting.audio_path or not Path(meeting.audio_path).exists():
        raise HTTPException(400, "Original audio is no longer available")

    meeting.status = "uploaded"
    meeting.progress = 0
    meeting.stage = "Queued"
    meeting.error = None
    db.commit()

    enqueue(db, meeting.id, "process")
    return meeting


@router.post("/{meeting_id}/resummarize", response_model=MeetingOut)
def resummarize(meeting_id: str, db: Session = Depends(get_db)):
    """Regenerate only the summary from the current (possibly edited) transcript."""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if not meeting.segments:
        raise HTTPException(400, "No transcript to summarize yet")

    meeting.status = "summarizing"
    meeting.progress = 85
    meeting.stage = "Queued for summary"
    meeting.error = None
    db.commit()

    enqueue(db, meeting.id, "summarize")
    return meeting


@router.patch("/{meeting_id}/segments/{segment_id}", response_model=SegmentOut)
def edit_segment(
    meeting_id: str, segment_id: str, body: SegmentUpdate, db: Session = Depends(get_db)
):
    """Correct a mis-transcribed segment. Language is re-detected; search stays
    consistent automatically (it queries the segments table)."""
    segment = db.get(TranscriptSegment, segment_id)
    if segment is None or segment.meeting_id != meeting_id:
        raise HTTPException(404, "Segment not found")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Segment text cannot be empty")

    segment.text = text
    segment.language = detect_language(text)
    db.commit()
    return segment


@router.post("/{meeting_id}/speakers/rename", response_model=list[SegmentOut])
def rename_speaker(meeting_id: str, body: SpeakerRename, db: Session = Depends(get_db)):
    """Rename a speaker across the whole meeting (e.g. 'Speaker 1' -> 'Priya')."""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    to_name = body.to_name.strip()
    if not to_name:
        raise HTTPException(400, "New speaker name cannot be empty")

    updated = 0
    for seg in meeting.segments:
        if seg.speaker == body.from_name:
            seg.speaker = to_name
            updated += 1
    if updated == 0:
        raise HTTPException(404, f"No segments with speaker '{body.from_name}'")
    db.commit()
    return meeting.segments
