"""OpenAI Whisper API transcription (whisper-1 with segment timestamps)."""

import httpx

from .base import STTProvider, TranscriptResult, TranscriptSegmentData

API_URL = "https://api.openai.com/v1/audio/transcriptions"


class OpenAIWhisperSTT(STTProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for STT_PROVIDER=openai")
        self.api_key = api_key

    async def transcribe(self, audio_path: str) -> TranscriptResult:
        async with httpx.AsyncClient(timeout=600) as client:
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={
                        "model": "whisper-1",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "segment",
                    },
                    files={"file": (audio_path.split("/")[-1], f)},
                )
        resp.raise_for_status()
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
            segments = [TranscriptSegmentData(start=0.0, end=0.0, text=data["text"])]

        return TranscriptResult(segments=segments, duration_seconds=data.get("duration"))
