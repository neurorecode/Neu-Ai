"""Shared helpers for chunked, retried STT calls.

Long meetings fan out into hundreds of ~30s chunk requests. Two things keep
that from failing:

  * post_with_retries — patient, jittered backoff that honours a 429
    Retry-After header, so a rate-limited chunk waits the right amount and
    succeeds instead of exhausting its tries.
  * run_chunked — bounded concurrency plus fault tolerance: a chunk that still
    fails after all retries is skipped (not fatal), so a single bad 30s slice
    never discards a 3-hour transcript. Only a large fraction of failures
    (systemic rate-limiting / bad key) fails the whole run.
"""

import asyncio
import logging
import random

import httpx

from ...config import settings

logger = logging.getLogger("neu.stt")


def _retry_delay(attempt: int, resp: httpx.Response | None) -> float:
    """Seconds to wait before the next attempt. Honour Retry-After on 429."""
    if resp is not None:
        retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 120.0) + random.uniform(0, 1.0)
            except ValueError:
                pass
    base = settings.stt_backoff_base * (2 ** (attempt - 1))
    return min(base, settings.stt_backoff_max) + random.uniform(0, 1.5)


async def post_with_retries(
    url: str,
    *,
    headers: dict,
    data: dict,
    file_path: str,
    file_field: str = "file",
    content_type: str = "audio/wav",
    timeout: float = 300.0,
) -> httpx.Response:
    """POST a multipart file upload, retrying on network errors and 429/5xx."""
    tries = max(1, settings.stt_max_retries)
    last_error: Exception | None = None
    for attempt in range(1, tries + 1):
        resp = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                with open(file_path, "rb") as f:
                    resp = await client.post(
                        url,
                        headers=headers,
                        data=data,
                        files={file_field: (file_path.split("/")[-1], f, content_type)},
                    )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"Retryable status {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            code = e.response.status_code if e.response is not None else None
            if code is not None and code < 500 and code != 429:
                raise  # non-retryable client error (bad key, bad request)
            last_error = e
        except httpx.HTTPError as e:
            last_error = e
        if attempt < tries:
            delay = _retry_delay(attempt, resp)
            logger.warning(
                "STT request failed (attempt %d/%d), retrying in %.0fs: %s",
                attempt, tries, delay, last_error,
            )
            await asyncio.sleep(delay)
    raise RuntimeError(f"STT request failed after {tries} attempts: {last_error}")


async def run_chunked(chunks, transcribe_chunk, on_progress=None):
    """Transcribe chunks concurrently (bounded), preserving order.

    `transcribe_chunk(chunk)` returns a list of TranscriptSegmentData with
    chunk-local timestamps; offsets are applied here. A chunk that fails after
    all retries is skipped so one bad slice can't discard a long meeting; the
    run only fails if too many chunks fail (see stt_max_failed_fraction).
    """
    semaphore = asyncio.Semaphore(max(1, settings.stt_concurrency))
    total = len(chunks)
    done_count = 0
    failed_count = 0
    lock = asyncio.Lock()

    async def worker(chunk):
        nonlocal done_count, failed_count
        segments = []
        async with semaphore:
            try:
                segments = await transcribe_chunk(chunk)
            except Exception as exc:
                async with lock:
                    failed_count += 1
                logger.error(
                    "Skipping chunk at %.0fs after retries: %s", chunk.offset, exc
                )
                segments = []
        for seg in segments:
            seg.start += chunk.offset
            seg.end += chunk.offset
        async with lock:
            done_count += 1
            if on_progress:
                on_progress(done_count / total)
        return segments

    results = await asyncio.gather(*(worker(c) for c in chunks))

    if total and failed_count / total > settings.stt_max_failed_fraction:
        raise RuntimeError(
            f"Transcription failed: {failed_count}/{total} chunks could not be "
            f"transcribed (likely provider rate limit or quota). Try again shortly."
        )
    if failed_count:
        logger.warning(
            "Transcription completed with %d/%d chunks skipped", failed_count, total
        )

    stitched = []
    for segments in results:
        stitched.extend(segments)
    stitched.sort(key=lambda s: s.start)
    return stitched
