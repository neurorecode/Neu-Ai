"""Job queue: dedup, crash recovery, and exhaustion behavior."""

from app.database import Base, SessionLocal, engine, run_sqlite_auto_migrations
from app.models import Job, Meeting
from app.services.jobs import enqueue, recover_stale_jobs


def setup_module():
    Base.metadata.create_all(bind=engine)
    run_sqlite_auto_migrations()


def _make_meeting(db, **kwargs) -> Meeting:
    meeting = Meeting(title="Job test", status="uploaded", **kwargs)
    db.add(meeting)
    db.commit()
    return meeting


def test_enqueue_deduplicates_queued_jobs():
    db = SessionLocal()
    try:
        meeting = _make_meeting(db)
        first = enqueue(db, meeting.id, "process")
        second = enqueue(db, meeting.id, "process")
        assert first.id == second.id

        # A different job type is a separate queue entry
        other = enqueue(db, meeting.id, "summarize")
        assert other.id != first.id
    finally:
        db.close()


def test_crash_recovery_requeues_running_jobs():
    db = SessionLocal()
    try:
        meeting = _make_meeting(db)
        job = Job(meeting_id=meeting.id, type="process", status="running", attempts=1)
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    recovered = recover_stale_jobs()
    assert recovered >= 1

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.status == "queued"
    finally:
        db.close()


def test_crash_recovery_fails_exhausted_jobs():
    db = SessionLocal()
    try:
        meeting = _make_meeting(db)
        job = Job(
            meeting_id=meeting.id, type="process",
            status="running", attempts=3, max_attempts=3,
        )
        db.add(job)
        db.commit()
        job_id, meeting_id = job.id, meeting.id
    finally:
        db.close()

    recover_stale_jobs()

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        meeting = db.get(Meeting, meeting_id)
        assert job.status == "failed"
        assert meeting.status == "failed"
        assert meeting.error
    finally:
        db.close()
