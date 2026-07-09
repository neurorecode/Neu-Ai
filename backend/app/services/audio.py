"""Audio normalization and chunking via ffmpeg.

All uploads are converted to 16 kHz mono WAV before transcription so every STT
provider receives a consistent, known-good input. Long recordings are split
into chunks (STT APIs have per-request limits) whose transcripts are stitched
back together with global timestamps.
"""

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AudioError(Exception):
    """Raised when a file cannot be decoded as audio."""


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_duration(path: str) -> float:
    """Return duration in seconds, raising AudioError for undecodable files."""
    proc = _run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ]
    )
    if proc.returncode != 0:
        raise AudioError(f"File is not a valid audio/video file: {proc.stderr.strip()[:300]}")
    try:
        duration = float(json.loads(proc.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise AudioError("Could not determine audio duration") from e
    if duration <= 0:
        raise AudioError("Audio file is empty (zero duration)")
    return duration


def _normalize_sync(src: str, dst: str) -> float:
    duration = probe_duration(src)
    proc = _run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", src,
            "-vn",              # drop any video stream
            "-ac", "1",         # mono
            "-ar", "16000",     # 16 kHz
            "-c:a", "pcm_s16le",
            dst,
        ]
    )
    if proc.returncode != 0:
        raise AudioError(f"Audio conversion failed: {proc.stderr.strip()[:300]}")
    return duration


async def normalize_audio(src: str) -> tuple[str, float]:
    """Convert src to 16 kHz mono WAV next to the original.

    Returns (wav_path, duration_seconds). Raises AudioError for corrupt input.
    If ffmpeg is unavailable (bare dev machine), the original file is passed
    through untouched with an unknown duration.
    """
    if not ffmpeg_available():
        return src, 0.0
    dst = str(Path(src).with_suffix(".norm.wav"))
    duration = await asyncio.to_thread(_normalize_sync, src, dst)
    return dst, duration


@dataclass
class AudioChunk:
    path: str
    offset: float  # global start time of this chunk in the full recording
    duration: float


def _split_sync(wav_path: str, chunk_seconds: float, overlap: float) -> list[AudioChunk]:
    total = probe_duration(wav_path)
    if total <= chunk_seconds:
        return [AudioChunk(path=wav_path, offset=0.0, duration=total)]

    chunks: list[AudioChunk] = []
    step = chunk_seconds - overlap
    start = 0.0
    index = 0
    base = Path(wav_path)
    while start < total:
        length = min(chunk_seconds, total - start)
        out = str(base.with_suffix(f".chunk{index:04d}.wav"))
        proc = _run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
                "-i", wav_path,
                "-c", "copy",
                out,
            ]
        )
        if proc.returncode != 0:
            raise AudioError(f"Chunk split failed: {proc.stderr.strip()[:300]}")
        chunks.append(AudioChunk(path=out, offset=start, duration=length))
        index += 1
        start += step
    return chunks


async def split_audio(
    wav_path: str, chunk_seconds: float = 600.0, overlap: float = 2.0
) -> list[AudioChunk]:
    """Split a WAV into chunks of chunk_seconds with a small overlap.

    Returns a single passthrough chunk when the file already fits.
    """
    if not ffmpeg_available():
        return [AudioChunk(path=wav_path, offset=0.0, duration=0.0)]
    return await asyncio.to_thread(_split_sync, wav_path, chunk_seconds, overlap)


def cleanup_chunks(chunks: list[AudioChunk], keep: str) -> None:
    """Delete temporary chunk files (but never the source WAV)."""
    for chunk in chunks:
        if chunk.path != keep:
            Path(chunk.path).unlink(missing_ok=True)
