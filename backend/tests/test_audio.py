"""Audio normalization & chunking tests (require ffmpeg)."""

import asyncio
from pathlib import Path

import pytest

from app.services.audio import (
    AudioError,
    cleanup_chunks,
    ffmpeg_available,
    normalize_audio,
    probe_duration,
    split_audio,
)

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")


@pytest.fixture()
def tone_file(tmp_path):
    """Generate a 12-second test tone as an m4a (a 'real' upload format)."""
    import subprocess

    path = tmp_path / "tone.m4a"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
            "-c:a", "aac", str(path),
        ],
        check=True,
    )
    return str(path)


def test_probe_duration(tone_file):
    assert 11.5 <= probe_duration(tone_file) <= 12.5


def test_probe_rejects_garbage(tmp_path):
    bad = tmp_path / "fake.wav"
    bad.write_bytes(b"this is not audio at all")
    with pytest.raises(AudioError):
        probe_duration(str(bad))


def test_normalize_produces_16k_mono_wav(tone_file):
    wav_path, duration = asyncio.run(normalize_audio(tone_file))
    assert wav_path.endswith(".norm.wav")
    assert Path(wav_path).exists()
    assert 11.5 <= duration <= 12.5

    import json
    import subprocess

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels", "-of", "json", wav_path,
        ],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["sample_rate"] == "16000"
    assert stream["channels"] == 1


def test_split_and_cleanup(tone_file):
    wav_path, _ = asyncio.run(normalize_audio(tone_file))
    chunks = asyncio.run(split_audio(wav_path, chunk_seconds=5.0, overlap=1.0))

    assert len(chunks) >= 3  # 12s in 5s chunks stepping 4s
    assert chunks[0].offset == 0.0
    # Offsets advance by chunk - overlap
    assert chunks[1].offset == pytest.approx(4.0, abs=0.1)
    for chunk in chunks:
        assert Path(chunk.path).exists()

    cleanup_chunks(chunks, keep=wav_path)
    assert Path(wav_path).exists()
    for chunk in chunks:
        if chunk.path != wav_path:
            assert not Path(chunk.path).exists()


def test_short_file_is_single_passthrough_chunk(tone_file):
    wav_path, _ = asyncio.run(normalize_audio(tone_file))
    chunks = asyncio.run(split_audio(wav_path, chunk_seconds=600.0))
    assert len(chunks) == 1
    assert chunks[0].path == wav_path
    assert chunks[0].offset == 0.0
