"""Shared helpers for chunked, retried STT calls."""

import asyncio
import logging

import httpx

logger = logging.getLogger("neu.stt")

MAX_TRIES = 3
BACKOFF_BASE = 2.0  # seconds: 2, 4 between tries
CONCURRENCY = 4


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
    last_error: Exception | None = None
    for attempt in range(1, MAX_TRIES + 1):
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
            if e.response is not None and e.response.status_code < 500 and e.response.status_code != 429:
                raise  # non-retryable client error (bad key, bad request)
            last_error = e
        except httpx.HTTPError as e:
            last_error = e
        if attempt < MAX_TRIES:
            delay = BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning("STT request failed (attempt %d/%d), retrying in %.0fs: %s",
                           attempt, MAX_TRIES, delay, last_error)
            await asyncio.sleep(delay)
    raise RuntimeError(f"STT request failed after {MAX_TRIES} attempts: {last_error}")


async def run_chunked(chunks, transcribe_chunk, on_progress=None):
    """Transcribe chunks concurrently (bounded), preserving order.

    `transcribe_chunk(chunk)` returns a list of TranscriptSegmentData with
    chunk-local timestamps; offsets are applied here. Progress is reported as
    completed_chunks / total_chunks.
    """
    semaphore = asyncio.Semaphore(CONCURRENCY)
    done_count = 0
    total = len(chunks)
    lock = asyncio.Lock()

    async def worker(chunk):
        nonlocal done_count
        async with semaphore:
            segments = await transcribe_chunk(chunk)
        for seg in segments:
            seg.start += chunk.offset
            seg.end += chunk.offset
        async with lock:
            done_count += 1
            if on_progress:
                on_progress(done_count / total)
        return segments

    results = await asyncio.gather(*(worker(c) for c in chunks))
    stitched = []
    for segments in results:
        stitched.extend(segments)
    stitched.sort(key=lambda s: s.start)
    return stitched
