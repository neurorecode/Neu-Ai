"""Persistent, DB-backed job queue.

Design goals for Phase 1 (single-node, no extra infra):
  - Jobs live in the `jobs` table, so a queued/interrupted job survives a
    process crash or restart.
  - One asyncio worker per process claims jobs sequentially (SQLite-friendly).
  - Crash recovery: on startup, any job stuck in `running` is re-queued unless
    it has exhausted its attempts.
  - Retries with exponential backoff between attempts.

The interface (enqueue / worker loop) is deliberately small so it can be
swapped for RQ/arq + Redis later without touching the pipeline code.
"""

import asyncio
import logging
from datetime import datetime, timezone

from ..database import SessionLocal
from ..models import Job, Meeting

logger = logging.getLogger("neu.jobs")

POLL_INTERVAL = 1.0
RETRY_BASE_DELAY = 5.0  # seconds; doubled per attempt


def enqueue(db, meeting_id: str, job_type: str = "process") -> Job:
    """Add a job for a meeting. Reuses an existing queued job of the same type
    to avoid duplicate work when a user double-clicks."""
    existing = (
        db.query(Job)
        .filter(Job.meeting_id == meeting_id, Job.type == job_type, Job.status == "queued")
        .first()
    )
    if existing:
        return existing
    job = Job(meeting_id=meeting_id, type=job_type)
    db.add(job)
    db.commit()
    return job


def recover_stale_jobs() -> int:
    """Re-queue jobs that were 'running' when the process died. Returns the
    number of jobs recovered. Called once at startup, before the worker."""
    db = SessionLocal()
    try:
        stale = db.query(Job).filter(Job.status == "running").all()
        recovered = 0
        for job in stale:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.error = (job.error or "") + " | abandoned after crash (max attempts reached)"
                _mark_meeting_failed(db, job.meeting_id, "Processing crashed and exhausted retries")
            else:
                job.status = "queued"
                recovered += 1
        db.commit()
        if stale:
            logger.info("Recovered %d stale job(s), failed %d", recovered, len(stale) - recovered)
        return recovered
    finally:
        db.close()


def _mark_meeting_failed(db, meeting_id: str, message: str) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is not None:
        meeting.status = "failed"
        meeting.error = message
        meeting.stage = None


def _claim_next_job() -> Job | None:
    db = SessionLocal()
    try:
        job = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at)
            .first()
        )
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def _finish_job(job_id: str, error: str | None) -> tuple[bool, str | None]:
    """Record the outcome. Returns (will_retry, meeting_id)."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return False, None
        if error is None:
            job.status = "done"
            job.error = None
            db.commit()
            return False, job.meeting_id
        job.error = error[:2000]
        if job.attempts < job.max_attempts:
            job.status = "queued"
            db.commit()
            return True, job.meeting_id
        job.status = "failed"
        _mark_meeting_failed(db, job.meeting_id, error[:2000])
        db.commit()
        return False, job.meeting_id
    finally:
        db.close()


async def _execute(job: Job) -> None:
    # Imported here to avoid a circular import (pipeline enqueues follow-ups).
    from .pipeline import process_meeting_job, summarize_meeting_job

    if job.type == "summarize":
        await summarize_meeting_job(job.meeting_id)
    else:
        await process_meeting_job(job.meeting_id)


async def worker_loop(stop_event: asyncio.Event) -> None:
    """Single-consumer worker. Runs until stop_event is set."""
    logger.info("Job worker started")
    while not stop_event.is_set():
        job = _claim_next_job()
        if job is None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
            continue

        logger.info("Running job %s (%s) attempt %d", job.id, job.type, job.attempts)
        error: str | None = None
        try:
            await _execute(job)
        except Exception as exc:  # noqa: BLE001 - job errors are recorded, not fatal
            logger.exception("Job %s failed", job.id)
            error = f"{type(exc).__name__}: {exc}"

        will_retry, _ = _finish_job(job.id, error)
        if will_retry:
            delay = RETRY_BASE_DELAY * (2 ** (job.attempts - 1))
            logger.info("Job %s will retry in %.0fs", job.id, delay)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
    logger.info("Job worker stopped")
