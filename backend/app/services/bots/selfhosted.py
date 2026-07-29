"""Self-hosted meeting-bot provider.

Talks to your OWN bot worker (SELFBOT_URL) over a tiny HTTP contract, so there
is no per-recording-hour Recall.ai charge. The worker joins the call, records
it, and exposes three endpoints:

    POST {url}/bots                {meeting_url, bot_name} -> {id, status}
    GET  {url}/bots/{id}           -> {status}
    GET  {url}/bots/{id}/recording -> {audio_url, audio_ext, speakers[]}

The worker speaks the normalized lifecycle vocabulary directly
(joining | recording | done | failed | left), so there is no status map to
maintain. `audio_url` may be:

  * an http(s):// URL the backend downloads (cross-container worker), or
  * a file:// path / bare filesystem path when the worker shares the upload
    volume with the backend (see services.bots.download).

Phase 1 ships a reference worker (selfbot/) with a mock mode — no browser — so
the whole invite -> record -> transcribe -> summarize path can be exercised end
to end. Phase 2 replaces the worker's internals with a headless-Chromium
(Playwright) bot that actually joins Google Meet; nothing in Neu changes.
"""

import httpx

from .base import (
    NORMALIZED_STATUSES,
    BotHandle,
    BotProvider,
    BotRecording,
    BotStatus,
    SpeakerTurn,
)


class SelfHostedBotProvider(BotProvider):
    def __init__(
        self,
        worker_url: str,
        token: str = "",
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not worker_url:
            raise ValueError("SELFBOT_URL is required for BOT_PROVIDER=selfhosted")
        self.base = worker_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # Injected only in tests (ASGI transport pointed at the reference worker).
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base, timeout=self.timeout, transport=self._transport
        )

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _normalize(status: str | None) -> str:
        s = (status or "").lower()
        return s if s in NORMALIZED_STATUSES else "joining"

    async def create_bot(self, meeting_url: str, bot_name: str, webhook_url: str | None) -> BotHandle:
        body = {"meeting_url": meeting_url, "bot_name": bot_name}
        async with self._client() as client:
            resp = await client.post("/bots", headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Self-hosted bot create failed ({resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        return BotHandle(
            provider_bot_id=str(data["id"]), status=self._normalize(data.get("status"))
        )

    async def get_status(self, provider_bot_id: str) -> BotStatus:
        async with self._client() as client:
            resp = await client.get(f"/bots/{provider_bot_id}", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return BotStatus(status=self._normalize(data.get("status")), raw=data)

    async def fetch_recording(self, provider_bot_id: str) -> BotRecording:
        async with self._client() as client:
            resp = await client.get(
                f"/bots/{provider_bot_id}/recording", headers=self._headers()
            )
        resp.raise_for_status()
        data = resp.json()
        audio_url = data.get("audio_url")
        if not audio_url:
            raise RuntimeError("Self-hosted bot recording is not ready (no audio_url)")

        speakers: list[SpeakerTurn] = []
        for turn in data.get("speakers") or []:
            start, end, name = turn.get("start"), turn.get("end"), turn.get("speaker")
            if start is not None and end is not None and name:
                speakers.append(SpeakerTurn(start=float(start), end=float(end), speaker=str(name)))

        return BotRecording(
            audio_url=audio_url,
            speakers=speakers,
            audio_ext=data.get("audio_ext") or ".wav",
        )
