"""Meeting-bot provider interface.

A bot joins a live video call (Google Meet / Zoom / Microsoft Teams), records
it, and hands back the audio plus a speaker timeline. That audio is then fed
into the existing transcription pipeline (services.pipeline), so Tamil /
English / Tanglish handling is identical to an uploaded recording.

Normalized bot lifecycle (provider-specific codes are mapped onto these):
    joining   -> the bot is connecting / waiting to be admitted
    recording -> in the call, recording
    done      -> recording finished and ready to fetch
    failed    -> could not join or errored
    left      -> the bot left / call ended without a usable recording
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

NORMALIZED_STATUSES = ("joining", "recording", "done", "failed", "left")


@dataclass
class BotHandle:
    provider_bot_id: str
    status: str  # one of NORMALIZED_STATUSES


@dataclass
class BotStatus:
    status: str
    raw: dict = field(default_factory=dict)


@dataclass
class SpeakerTurn:
    """A stretch of time attributed to one participant, in seconds from the
    start of the recording. Used to label transcript segments with real
    participant names (better than generic 'Speaker N')."""

    start: float
    end: float
    speaker: str


@dataclass
class BotRecording:
    audio_url: str  # pre-signed URL to download the recording (audio or A/V)
    speakers: list[SpeakerTurn] = field(default_factory=list)
    audio_ext: str = ".mp4"  # container of the downloaded media


class BotProvider(ABC):
    @abstractmethod
    async def create_bot(self, meeting_url: str, bot_name: str, webhook_url: str | None) -> BotHandle:
        """Dispatch a bot to the meeting. Returns the provider's bot id + status."""

    @abstractmethod
    async def get_status(self, provider_bot_id: str) -> BotStatus:
        """Poll the bot's current normalized status."""

    @abstractmethod
    async def fetch_recording(self, provider_bot_id: str) -> BotRecording:
        """Once status == 'done', return the recording download URL and speaker timeline."""
