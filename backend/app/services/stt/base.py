from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

# Reports transcription progress as a fraction in [0, 1].
ProgressCallback = Callable[[float], None]


@dataclass
class TranscriptSegmentData:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class TranscriptResult:
    segments: list[TranscriptSegmentData] = field(default_factory=list)
    duration_seconds: float | None = None


class STTProvider(ABC):
    """Speech-to-text provider interface.

    Implementations must handle Tamil, English, and code-mixed (Tanglish)
    audio. Language tagging happens downstream in services.language — the
    provider only needs to return faithful text with timestamps.

    `audio_path` is a normalized 16 kHz mono WAV (see services.audio). Long
    recordings should be chunked internally; report progress via on_progress.
    """

    @abstractmethod
    async def transcribe(
        self, audio_path: str, on_progress: ProgressCallback | None = None
    ) -> TranscriptResult: ...
