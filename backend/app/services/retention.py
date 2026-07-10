"""Audio retention & disk hygiene.

Recordings are the only large artifact Neu keeps on disk. At a handful of
meetings a day they add up fast, so this background sweep:

  1. Removes orphaned working files (`*.norm.wav`, `*.chunk*.wav`) left behind
     by a crashed/interrupted pipeline run — always safe, they're regenerable.
  2. If AUDIO_RETENTION_DAYS > 0, deletes original recordings older than that
     many days and clears the meeting's audio_path. The transcript and summary
     (the valuable, tiny part) are kept forever; only playback is lost.

Default retention is 0 (keep audio forever), so this never deletes a user's
recording unless they opt in by setting AUDIO_RETENTION_DAYS.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import settings
from ..database import SessionLocal
from ..models import Meeting

logger = logging.getLogger("neu.retention")

# Don't touch working files younger than this — a pipeline run may still be
# using them.
ORPHAN_MIN_AGE_SECONDS = 3600  # 1 hour


def _sweep_orphan_temp_files() -> int:
    """Delete stale normalized/chunk WAVs. Returns count removed."""
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return 0
    removed = 0
    cutoff = time.time() - ORPHAN_MIN_AGE_SECONDS
    for pattern in ("*.norm.wav", "*.chunk*.wav"):
        for path in upload_dir.glob(pattern):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                logger.warning("Could not remove temp file %s", path, exc_info=True)
    return removed


def _purge_old_recordings() -> int:
    """Delete original recordings past the retention window. Returns count."""
    days = settings.audio_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    purged = 0
    db = SessionLocal()
    try:
        candidates = (
            db.query(Meeting)
            .filter(Meeting.audio_path.isnot(None), Meeting.created_at < cutoff)
            .all()
        )
        for meeting in candidates:
            path = Path(meeting.audio_path)
            try:
                path.unlink(missing_ok=True)
                # Also drop any leftover normalized working file.
                path.with_suffix(".norm.wav").unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not delete recording %s", path, exc_info=True)
                continue
            meeting.audio_path = None
            purged += 1
        if purged:
            db.commit()
    finally:
        db.close()
    return purged


def sweep_once() -> tuple[int, int]:
    """Run one retention pass. Returns (orphans_removed, recordings_purged)."""
    orphans = _sweep_orphan_temp_files()
    purged = _purge_old_recordings()
    if orphans or purged:
        logger.info("Retention sweep: %d temp files removed, %d recordings purged", orphans, purged)
    return orphans, purged


async def retention_loop(stop_event: asyncio.Event) -> None:
    interval = max(settings.retention_sweep_hours, 0.5) * 3600
    logger.info(
        "Retention sweep started (every %.1fh, audio kept %s)",
        settings.retention_sweep_hours,
        f"{settings.audio_retention_days}d" if settings.audio_retention_days > 0 else "forever",
    )
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(sweep_once)
        except Exception:
            logger.exception("Retention sweep failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    logger.info("Retention sweep stopped")
