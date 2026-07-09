"""Sarvam AI speech-to-text (saarika model).

Best-in-class for Indian languages including Tamil and heavily code-mixed
Tamil-English speech. https://docs.sarvam.ai

The synchronous endpoint accepts short clips (~30s), so long recordings are
split into chunks (services.audio) and transcribed concurrently with retries;
timestamps are re-based onto the full recording.
"""

from ...config import settings
from ..audio import cleanup_chunks, split_audio
from .base import ProgressCallback, STTProvider, TranscriptResult, TranscriptSegmentData
from .util import post_with_retries, run_chunked

API_URL = "https://api.sarvam.ai/speech-to-text"


class SarvamSTT(STTProvider):
    def __init__(self, api_key: str, model: str = "saarika:v2.5"):
        if not api_key:
            raise ValueError("SARVAM_API_KEY is required for STT_PROVIDER=sarvam")
        self.api_key = api_key
        self.model = model

    async def _transcribe_chunk(self, chunk) -> list[TranscriptSegmentData]:
        resp = await post_with_retries(
            API_URL,
            headers={"api-subscription-key": self.api_key},
            data={
                "model": self.model,
                # unknown lets saarika auto-detect and handle
                # Tamil / English / code-mixed speech
                "language_code": "unknown",
                "with_timestamps": "true",
            },
            file_path=chunk.path,
        )
        data = resp.json()

        segments: list[TranscriptSegmentData] = []
        timestamps = data.get("timestamps") or {}
        words = timestamps.get("words") or []
        starts = timestamps.get("start_time_seconds") or []
        ends = timestamps.get("end_time_seconds") or []

        if words and starts and ends:
            # Group word-level timestamps into utterance-sized spans.
            chunk_words: list[str] = []
            span_start = starts[0]
            for word, w_start, w_end in zip(words, starts, ends):
                chunk_words.append(word)
                if w_end - span_start >= 12.0 or word.endswith((".", "?", "!", "।")):
                    segments.append(
                        TranscriptSegmentData(start=span_start, end=w_end, text=" ".join(chunk_words))
                    )
                    chunk_words = []
                    span_start = w_end
            if chunk_words:
                segments.append(
                    TranscriptSegmentData(start=span_start, end=ends[-1], text=" ".join(chunk_words))
                )
        else:
            transcript = (data.get("transcript") or "").strip()
            if transcript:
                segments.append(
                    TranscriptSegmentData(start=0.0, end=chunk.duration, text=transcript)
                )
        return segments

    async def transcribe(
        self, audio_path: str, on_progress: ProgressCallback | None = None
    ) -> TranscriptResult:
        chunks = await split_audio(
            audio_path, chunk_seconds=settings.sarvam_chunk_seconds, overlap=0.0
        )
        try:
            segments = await run_chunked(chunks, self._transcribe_chunk, on_progress)
        finally:
            cleanup_chunks(chunks, keep=audio_path)

        duration = segments[-1].end if segments and segments[-1].end else None
        return TranscriptResult(segments=segments, duration_seconds=duration)
