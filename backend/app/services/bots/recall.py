"""Recall.ai meeting-bot provider.

One API covers Google Meet, Zoom, and Microsoft Teams. Docs: https://docs.recall.ai

Flow:
  POST {region}.recall.ai/api/v1/bot  {meeting_url, bot_name, recording_config}
     -> bot id; the bot joins and records
  A webhook (bot.status_change / recording done) tells us when status == "done"
  GET {region}.recall.ai/api/v1/bot/{id}  -> recording with a pre-signed
     download_url, plus participant events we turn into a speaker timeline

Auth header is the raw key with a "Token " prefix (NOT "Bearer").
"""

import logging

import httpx

from .base import BotHandle, BotProvider, BotRecording, BotStatus, SpeakerTurn

logger = logging.getLogger("neu.bots.recall")

# Recall status codes -> our normalized lifecycle.
# NOTE: `call_ended` is NOT a failure — the call ended normally and Recall is
# finalizing the recording; the terminal success status is `done`. Treat it as
# still-in-progress so the poller keeps checking until the recording is ready.
STATUS_MAP = {
    "ready": "joining",
    "joining_call": "joining",
    "in_waiting_room": "joining",
    "in_call_not_recording": "joining",
    "recording_permission_allowed": "recording",
    "in_call_recording": "recording",
    "call_ended": "recording",       # recording being finalized -> wait for done
    "recording_done": "done",
    "analysis_done": "done",
    "done": "done",
    "fatal": "failed",
    "recording_permission_denied": "failed",
    "bot_rejected": "failed",
    "media_expired": "failed",
}


class RecallBotProvider(BotProvider):
    def __init__(self, api_key: str, region: str = "us-west-2"):
        if not api_key:
            raise ValueError("RECALL_API_KEY is required for BOT_PROVIDER=recall")
        self.api_key = api_key
        self.base = f"https://{region}.recall.ai/api/v1"

    def _headers(self) -> dict:
        return {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _normalize(code: str | None) -> str:
        return STATUS_MAP.get(code or "", "joining")

    async def create_bot(self, meeting_url: str, bot_name: str, webhook_url: str | None) -> BotHandle:
        # Record mixed audio; we run our own (Sarvam) transcription downstream.
        # We do NOT register a per-bot realtime webhook here — bot status
        # changes aren't a valid realtime-endpoint event. Completion is driven
        # by the status poller (bot_service.bot_poll_loop); for push instead of
        # poll, configure an account-level webhook to /api/bots/webhook/<secret>
        # in the Recall dashboard.
        body: dict = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "recording_config": {"audio_mixed": {}},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base}/bot", headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"Recall create_bot failed ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        status_code = None
        if data.get("status_changes"):
            status_code = data["status_changes"][-1].get("code")
        return BotHandle(provider_bot_id=data["id"], status=self._normalize(status_code))

    async def _retrieve(self, provider_bot_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.base}/bot/{provider_bot_id}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def get_status(self, provider_bot_id: str) -> BotStatus:
        data = await self._retrieve(provider_bot_id)
        changes = data.get("status_changes") or []
        code = changes[-1].get("code") if changes else None
        return BotStatus(status=self._normalize(code), raw=data)

    async def fetch_recording(self, provider_bot_id: str) -> BotRecording:
        data = await self._retrieve(provider_bot_id)

        # Recording download URL — schema has shifted across Recall versions, so
        # probe the common shapes (recordings[].media_shortcuts / media_shortcuts).
        audio_url = _find_download_url(data)
        if not audio_url:
            raise RuntimeError("Recall recording is not ready or download URL not found")

        speakers = _participant_timeline(data)
        ext = ".mp3" if ".mp3" in audio_url.split("?")[0] else ".mp4"
        return BotRecording(audio_url=audio_url, speakers=speakers, audio_ext=ext)


def _find_download_url(data: dict) -> str | None:
    # Newer: recordings[].media_shortcuts.audio_mixed.data.download_url
    for rec in data.get("recordings") or []:
        shortcuts = rec.get("media_shortcuts") or {}
        for key in ("audio_mixed", "video_mixed"):
            node = shortcuts.get(key) or {}
            url = (node.get("data") or {}).get("download_url")
            if url:
                return url
    # Older: top-level media_shortcuts / audio urls
    shortcuts = data.get("media_shortcuts") or {}
    for key in ("audio_mixed", "video_mixed"):
        node = shortcuts.get(key) or {}
        url = (node.get("data") or {}).get("download_url")
        if url:
            return url
    return None


def _participant_timeline(data: dict) -> list[SpeakerTurn]:
    """Build a speaker timeline from Recall participant speech events, if present."""
    turns: list[SpeakerTurn] = []
    events = (
        data.get("speaker_timeline")
        or (data.get("recordings") or [{}])[0].get("speaker_timeline")
        or []
    )
    for ev in events:
        name = ev.get("name") or ev.get("participant", {}).get("name")
        start = ev.get("start_time") or ev.get("timestamp")
        end = ev.get("end_time")
        if name is not None and start is not None and end is not None:
            turns.append(SpeakerTurn(start=float(start), end=float(end), speaker=str(name)))
    return turns
