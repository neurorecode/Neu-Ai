"""Mock meeting-bot provider — lets the full invite → join → recording →
pipeline flow be exercised without a Recall.ai account.

`create_bot` returns immediately as 'done' and `fetch_recording` hands back a
bundled demo recording (the same Tanglish stand-up the mock STT uses), with a
synthetic speaker timeline carrying real names."""

from pathlib import Path

from .base import BotHandle, BotProvider, BotRecording, BotStatus, SpeakerTurn

# Speaker timeline mirroring the mock STT demo transcript, so bot-sourced
# meetings get real participant names end-to-end in tests/demos.
DEMO_SPEAKERS = [
    SpeakerTurn(0.0, 6.5, "Priya"),
    SpeakerTurn(6.5, 14.0, "Karthik"),
    SpeakerTurn(14.0, 30.5, "Priya"),
    SpeakerTurn(30.5, 47.5, "Divya"),
    SpeakerTurn(47.5, 54.0, "Divya"),
    SpeakerTurn(54.0, 72.0, "Arjun"),
    SpeakerTurn(72.0, 96.0, "Priya"),
    SpeakerTurn(96.0, 108.0, "Divya"),
]


class MockBotProvider(BotProvider):
    async def create_bot(self, meeting_url: str, bot_name: str, webhook_url: str | None) -> BotHandle:
        return BotHandle(provider_bot_id=f"mock-bot-{abs(hash(meeting_url)) % 10_000}", status="done")

    async def get_status(self, provider_bot_id: str) -> BotStatus:
        return BotStatus(status="done", raw={"mock": True})

    async def fetch_recording(self, provider_bot_id: str) -> BotRecording:
        # Point at a bundled demo wav so the download step has a real file.
        demo = Path(__file__).resolve().parents[3] / "tests" / "data" / "demo_meeting.wav"
        return BotRecording(
            audio_url=f"file://{demo}",
            speakers=DEMO_SPEAKERS,
            audio_ext=".wav",
        )
