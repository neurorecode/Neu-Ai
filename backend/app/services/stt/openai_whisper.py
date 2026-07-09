"""OpenAI Whisper API transcription (whisper-1 with segment timestamps).

The API caps uploads at 25 MB, so long recordings are chunked (~10 min of
16 kHz mono WAV per chunk) and stitched with re-based timestamps.
"""

from ...config import settings
from ..audio import cleanup_chunks, split_audio
from .base import ProgressCallback, STTProvider, TranscriptResult, TranscriptSegmentData
from .util import post_with_retries, run_chunked

API_URL = "https://api.openai.com/v1/audio/transcriptions"


class OpenAIWhisperSTT(STTProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for STT_PROVIDER=openai")
        self.api_key = api_key

    async def _transcribe_chunk(self, chunk) -> list[TranscriptSegmentData]:
        resp = await post_with_retries(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            data={
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
            },
            file_path=chunk.path,
            timeout=600.0,
        )
        data = resp.json()

        segments = [
            TranscriptSegmentData(
                start=float(s.get("start", 0.0)),
                end=float(s.get("end", 0.0)),
                text=(s.get("text") or "").strip(),
            )
            for s in data.get("segments", [])
            if (s.get("text") or "").strip()
        ]
        if not segments and data.get("text"):
            segments = [
                TranscriptSegmentData(start=0.0, end=chunk.duration, text=data["text"])
            ]
        return segments

    async def transcribe(
        self, audio_path: str, on_progress: ProgressCallback | None = None
    ) -> TranscriptResult:
        chunks = await split_audio(
            audio_path, chunk_seconds=settings.openai_chunk_seconds, overlap=0.0
        )
        try:
            segments = await run_chunked(chunks, self._transcribe_chunk, on_progress)
        finally:
            cleanup_chunks(chunks, keep=audio_path)

        duration = segments[-1].end if segments and segments[-1].end else None
        return TranscriptResult(segments=segments, duration_seconds=duration)
