import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Meeting, TranscriptSegment, User, WorkspaceMember
from ..schemas import (
    MeetingDetail,
    MeetingOut,
    SearchHit,
    SegmentOut,
    SegmentUpdate,
    ShareOut,
    SpeakerRename,
)
from ..services.auth import default_workspace_id, get_current_user, get_membership, require_role
from ..services.jobs import enqueue
from ..services.language import detect_language

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac"}

AUDIO_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
}


def _get_meeting_checked(
    db: Session, user: User, meeting_id: str, *, write: bool = False
) -> Meeting:
    """Load a meeting and verify the user can access it (and modify it when
    write=True — viewers are read-only)."""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    if meeting.workspace_id is not None:
        member = get_membership(db, user, meeting.workspace_id)
        if write:
            require_role(member, "owner", "member")
    return meeting


@router.get("", response_model=list[MeetingOut])
def list_meetings(
    workspace_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id is None:
        workspace_id = default_workspace_id(db, user)
    get_membership(db, user, workspace_id)
    return (
        db.query(Meeting)
        .filter(Meeting.workspace_id == workspace_id)
        .order_by(Meeting.created_at.desc())
        .all()
    )


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
    file: UploadFile = File(...),
    title: str = Form("Untitled meeting"),
    workspace_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "audio.webm").suffix.lower() or ".webm"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'")

    if workspace_id is None:
        workspace_id = default_workspace_id(db, user)
    member = get_membership(db, user, workspace_id)
    require_role(member, "owner", "member")

    meeting = Meeting(
        title=title.strip() or "Untitled meeting",
        status="uploaded",
        workspace_id=workspace_id,
        created_by=user.id,
    )
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
def search(
    q: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = q.strip()
    if not q:
        return []
    pattern = f"%{q}%"

    workspace_ids = [
        m.workspace_id
        for m in db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()
    ]
    if not workspace_ids:
        return []

    hits: list[SearchHit] = []
    seg_rows = (
        db.query(TranscriptSegment, Meeting)
        .join(Meeting, TranscriptSegment.meeting_id == Meeting.id)
        .filter(
            Meeting.workspace_id.in_(workspace_ids),
            TranscriptSegment.text.like(pattern),
        )
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

    title_rows = (
        db.query(Meeting)
        .filter(Meeting.workspace_id.in_(workspace_ids), Meeting.title.like(pattern))
        .limit(20)
        .all()
    )
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
def get_meeting(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_meeting_checked(db, user, meeting_id)


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = _get_meeting_checked(db, user, meeting_id, write=True)
    if meeting.audio_path:
        base = Path(meeting.audio_path)
        base.unlink(missing_ok=True)
        base.with_suffix(".norm.wav").unlink(missing_ok=True)
    db.delete(meeting)
    db.commit()


def _audio_response(meeting: Meeting) -> FileResponse:
    if not meeting.audio_path:
        raise HTTPException(404, "No audio for this meeting")
    path = Path(meeting.audio_path)
    if not path.exists():
        raise HTTPException(404, "Audio file no longer available")
    media_type = AUDIO_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    # FileResponse handles HTTP Range requests, so <audio> seeking works.
    return FileResponse(path, media_type=media_type, filename=f"{meeting.title}{path.suffix}")


@router.get("/{meeting_id}/audio")
def meeting_audio(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = _get_meeting_checked(db, user, meeting_id)
    return _audio_response(meeting)


@router.post("/{meeting_id}/share", response_model=ShareOut)
def enable_share(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = _get_meeting_checked(db, user, meeting_id, write=True)
    if not meeting.share_token:
        meeting.share_token = uuid.uuid4().hex
        db.commit()
    return ShareOut(share_token=meeting.share_token)


@router.delete("/{meeting_id}/share", response_model=ShareOut)
def disable_share(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = _get_meeting_checked(db, user, meeting_id, write=True)
    meeting.share_token = None
    db.commit()
    return ShareOut(share_token=None)


@router.post("/{meeting_id}/reprocess", response_model=MeetingOut)
def reprocess(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run the full pipeline (transcription + summary) from the original audio."""
    meeting = _get_meeting_checked(db, user, meeting_id, write=True)
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
def resummarize(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate only the summary from the current (possibly edited) transcript."""
    meeting = _get_meeting_checked(db, user, meeting_id, write=True)
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
    meeting_id: str,
    segment_id: str,
    body: SegmentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Correct a mis-transcribed segment. Language is re-detected; search stays
    consistent automatically (it queries the segments table)."""
    _get_meeting_checked(db, user, meeting_id, write=True)
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
def rename_speaker(
    meeting_id: str,
    body: SpeakerRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename a speaker across the whole meeting (e.g. 'Speaker 1' -> 'Priya')."""
    meeting = _get_meeting_checked(db, user, meeting_id, write=True)
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


# --- public share-link access (no auth) --------------------------------------

shared_router = APIRouter(prefix="/api/shared", tags=["sharing"])


def _get_shared_meeting(db: Session, token: str) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.share_token == token).first()
    if meeting is None:
        raise HTTPException(404, "This share link is invalid or has been revoked")
    return meeting


@shared_router.get("/{token}", response_model=MeetingDetail)
def shared_meeting(token: str, db: Session = Depends(get_db)):
    return _get_shared_meeting(db, token)


@shared_router.get("/{token}/audio")
def shared_meeting_audio(token: str, db: Session = Depends(get_db)):
    return _audio_response(_get_shared_meeting(db, token))
