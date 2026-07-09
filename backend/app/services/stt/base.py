from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
    """

    @abstractmethod
    async def transcribe(self, audio_path: str) -> TranscriptResult: ...
