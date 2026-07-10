"""Audio retention: orphan temp-file cleanup + recording purge past the window."""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import Meeting, TranscriptSegment
from app.services import retention


def _make_meeting(db, *, age_days: int, with_audio: bool = True) -> Meeting:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    meeting = Meeting(title="Retention test", status="completed")
    meeting.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.add(meeting)
    db.flush()  # assigns meeting.id
    if with_audio:
        audio = upload_dir / f"{meeting.id}.mp3"
        audio.write_bytes(b"fake-audio")
        meeting.audio_path = str(audio)
    # A transcript that must survive the purge.
    db.add(TranscriptSegment(meeting_id=meeting.id, start=0, end=1, text="hello"))
    db.commit()
    return meeting


def test_purge_disabled_by_default(monkeypatch, client):
    monkeypatch.setattr(settings, "audio_retention_days", 0)
    db = SessionLocal()
    try:
        m = _make_meeting(db, age_days=999)
        path = Path(m.audio_path)
        assert path.exists()
        retention.sweep_once()
        db.refresh(m)
        # 0 == keep forever: nothing removed.
        assert m.audio_path is not None
        assert path.exists()
    finally:
        db.close()


def test_purge_old_recording_keeps_transcript(monkeypatch, client):
    monkeypatch.setattr(settings, "audio_retention_days", 30)
    db = SessionLocal()
    try:
        old = _make_meeting(db, age_days=45)
        recent = _make_meeting(db, age_days=5)
        old_path = Path(old.audio_path)
        recent_path = Path(recent.audio_path)

        _, purged = retention.sweep_once()
        assert purged >= 1  # at least the 45-day-old one (DB is shared across tests)

        db.refresh(old)
        db.refresh(recent)
        # Old recording gone; transcript preserved.
        assert old.audio_path is None
        assert not old_path.exists()
        assert len(old.segments) == 1
        assert old.has_audio is False
        # Recent recording untouched.
        assert recent.audio_path is not None
        assert recent_path.exists()
    finally:
        db.close()


def test_orphan_norm_wav_removed(monkeypatch, client):
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stale = upload_dir / "abandoned.norm.wav"
    stale.write_bytes(b"x")
    fresh = upload_dir / "inflight.norm.wav"
    fresh.write_bytes(b"x")
    # Age the stale file past the 1h orphan threshold; keep the fresh one new.
    old_ts = time.time() - retention.ORPHAN_MIN_AGE_SECONDS - 60
    os.utime(stale, (old_ts, old_ts))

    removed = retention._sweep_orphan_temp_files()
    assert removed >= 1
    assert not stale.exists()
    assert fresh.exists()  # too young to touch — a run may still be using it
