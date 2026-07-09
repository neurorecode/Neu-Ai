"""Sarvam AI speech-to-text (saarika model).

Best-in-class for Indian languages including Tamil and heavily code-mixed
Tamil-English speech. https://docs.sarvam.ai
"""

import httpx

from .base import STTProvider, TranscriptResult, TranscriptSegmentData

API_URL = "https://api.sarvam.ai/speech-to-text"


class SarvamSTT(STTProvider):
    def __init__(self, api_key: str, model: str = "saarika:v2.5"):
        if not api_key:
            raise ValueError("SARVAM_API_KEY is required for STT_PROVIDER=sarvam")
        self.api_key = api_key
        self.model = model

    async def transcribe(self, audio_path: str) -> TranscriptResult:
        async with httpx.AsyncClient(timeout=300) as client:
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    API_URL,
                    headers={"api-subscription-key": self.api_key},
                    data={
                        "model": self.model,
                        # unknown lets saarika auto-detect and handle
                        # Tamil / English / code-mixed speech
                        "language_code": "unknown",
                        "with_timestamps": "true",
                    },
                    files={"file": (audio_path.split("/")[-1], f, "audio/wav")},
                )
        resp.raise_for_status()
        data = resp.json()

        segments: list[TranscriptSegmentData] = []
        timestamps = data.get("timestamps") or {}
        words = timestamps.get("words") or []
        starts = timestamps.get("start_time_seconds") or []
        ends = timestamps.get("end_time_seconds") or []

        if words and starts and ends:
            # Group word-level timestamps into ~12s utterance chunks.
            chunk_words: list[str] = []
            chunk_start = starts[0]
            for word, w_start, w_end in zip(words, starts, ends):
                chunk_words.append(word)
                if w_end - chunk_start >= 12.0 or word.endswith((".", "?", "!", "।")):
                    segments.append(
                        TranscriptSegmentData(
                            start=chunk_start, end=w_end, text=" ".join(chunk_words)
                        )
                    )
                    chunk_words = []
                    chunk_start = w_end
            if chunk_words:
                segments.append(
                    TranscriptSegmentData(start=chunk_start, end=ends[-1], text=" ".join(chunk_words))
                )
        else:
            transcript = data.get("transcript", "")
            if transcript:
                segments.append(TranscriptSegmentData(start=0.0, end=0.0, text=transcript))

        duration = segments[-1].end if segments and segments[-1].end else None
        return TranscriptResult(segments=segments, duration_seconds=duration)
