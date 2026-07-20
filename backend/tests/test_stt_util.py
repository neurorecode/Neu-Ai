"""STT resilience: a few failed chunks are skipped, not fatal; too many fail."""

import asyncio
import types

import pytest

from app.config import settings
from app.services.stt.base import TranscriptSegmentData
from app.services.stt.util import run_chunked


def _chunk(offset):
    return types.SimpleNamespace(path=f"/tmp/c{offset}.wav", offset=float(offset), duration=29.0)


def _seg(text="hi"):
    return [TranscriptSegmentData(start=0.0, end=5.0, text=text)]


def test_skips_a_failed_chunk_and_keeps_the_rest(monkeypatch):
    monkeypatch.setattr(settings, "stt_max_failed_fraction", 0.15)
    chunks = [_chunk(i * 29) for i in range(10)]

    async def transcribe(chunk):
        if chunk.offset == 87:  # one chunk always fails
            raise RuntimeError("Retryable status 429")
        return _seg()

    segs = asyncio.run(run_chunked(chunks, transcribe))
    # 9 of 10 chunks succeeded — one skipped, transcript preserved.
    assert len(segs) == 9


def test_fails_when_too_many_chunks_fail(monkeypatch):
    monkeypatch.setattr(settings, "stt_max_failed_fraction", 0.15)
    chunks = [_chunk(i * 29) for i in range(10)]

    async def transcribe(chunk):
        if chunk.offset < 29 * 5:  # half the chunks fail -> systemic
            raise RuntimeError("Retryable status 429")
        return _seg()

    with pytest.raises(RuntimeError, match="could not be transcribed"):
        asyncio.run(run_chunked(chunks, transcribe))


def test_offsets_are_applied(monkeypatch):
    monkeypatch.setattr(settings, "stt_max_failed_fraction", 0.15)
    chunks = [_chunk(0), _chunk(29)]

    async def transcribe(chunk):
        return _seg()

    segs = asyncio.run(run_chunked(chunks, transcribe))
    assert sorted(s.start for s in segs) == [0.0, 29.0]
