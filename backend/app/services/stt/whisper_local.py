"""Local transcription via faster-whisper (no API key, runs on-device).

Requires: pip install faster-whisper
Whisper's multilingual models handle Tamil and English; code-mixed speech is
transcribed with mixed script, which the language tagger classifies as
tanglish downstream.
"""

import asyncio

from .base import STTProvider, TranscriptResult, TranscriptSegmentData


class LocalWhisperSTT(STTProvider):
    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise RuntimeError(
                    "faster-whisper is not installed. Run: pip install faster-whisper"
                ) from e
            self._model = WhisperModel(self.model_size, compute_type="int8")
        return self._model

    def _transcribe_sync(self, audio_path: str) -> TranscriptResult:
        model = self._load()
        raw_segments, info = model.transcribe(audio_path, vad_filter=True)
        segments = [
            TranscriptSegmentData(start=s.start, end=s.end, text=s.text.strip())
            for s in raw_segments
            if s.text.strip()
        ]
        return TranscriptResult(segments=segments, duration_seconds=getattr(info, "duration", None))

    async def transcribe(self, audio_path: str) -> TranscriptResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)
