import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Meeting, TranscriptSegment
from ..schemas import MeetingDetail, MeetingOut, SearchHit
from ..services.pipeline import process_meeting

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"}


@router.get("", response_model=list[MeetingOut])
def list_meetings(db: Session = Depends(get_db)):
    return db.query(Meeting).order_by(Meeting.created_at.desc()).all()


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(process_meeting, meeting.id)
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
        Path(meeting.audio_path).unlink(missing_ok=True)
    db.delete(meeting)
    db.commit()


@router.post("/{meeting_id}/reprocess", response_model=MeetingOut)
def reprocess(meeting_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if not meeting.audio_path or not Path(meeting.audio_path).exists():
        raise HTTPException(400, "Original audio is no longer available")

    for seg in list(meeting.segments):
        db.delete(seg)
    if meeting.summary:
        db.delete(meeting.summary)
    meeting.status = "uploaded"
    meeting.error = None
    db.commit()

    background_tasks.add_task(process_meeting, meeting.id)
    return meeting
