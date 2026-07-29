# Neu AI self-hosted meeting-bot worker

This is Neu's **own** meeting bot — the alternative to paying Recall.ai per
recording-hour. Neu's backend talks to it over a tiny HTTP contract, so the bot
is a completely separate service you can run, restart, and upgrade on its own.

```
Neu backend  ──HTTP──▶  selfbot worker  ──joins──▶  Google Meet / Zoom / Teams
(SelfHostedBotProvider)                  ──records──▶ audio ──▶ back to Neu's pipeline
```

Because it plugs into Neu's existing `BotProvider` abstraction, **nothing else
in Neu changes** — the recording flows into the same Sarvam transcription and
Sonnet 5 summary as an uploaded file or a Recall recording.

## Phases

- **Phase 1 (this):** `SELFBOT_MODE=mock` — no browser. Simulates a bot that
  joins, records for a few seconds, then finishes and hands back a bundled demo
  recording. This proves the whole `invite → record → transcribe → summarize`
  path works end to end with your own worker, **before** investing in browser
  automation.
- **Phase 2 (next):** `SELFBOT_MODE=meet` — a headless-Chromium (Playwright)
  bot that actually joins Google Meet and captures the call audio. The HTTP
  contract stays identical, so switching is just a mode flag.

## HTTP contract

| Method & path              | Purpose                                   |
| -------------------------- | ----------------------------------------- |
| `POST /bots`               | `{meeting_url, bot_name}` → `{id, status}` |
| `GET  /bots/{id}`          | → `{status}`                              |
| `GET  /bots/{id}/recording`| → `{audio_url, audio_ext, speakers[]}`    |
| `GET  /bots/{id}/audio`    | → recorded audio bytes                    |
| `GET  /health`             | → `{ok, mode}`                            |

Statuses use Neu's normalized vocabulary: `joining · recording · done · failed · left`.

## Configuration (env)

| Variable                    | Default                  | Meaning                                        |
| --------------------------- | ------------------------ | ---------------------------------------------- |
| `SELFBOT_MODE`              | `mock`                   | `mock` (Phase 1) or `meet` (Phase 2)           |
| `SELFBOT_TOKEN`             | *(empty)*                | If set, control endpoints require `Authorization: Bearer <token>` (must match the backend's `SELFBOT_TOKEN`) |
| `SELFBOT_PUBLIC_URL`        | `http://localhost:8080`  | URL the Neu backend uses to reach this worker  |
| `SELFBOT_DEMO_WAV`          | `/data/demo_meeting.wav` | Recording the mock worker returns              |
| `SELFBOT_MOCK_JOIN_SECONDS` | `3`                      | Mock: simulated "joining" duration             |
| `SELFBOT_MOCK_RECORD_SECONDS`| `6`                     | Mock: simulated "recording" duration           |

## Point Neu at it

In `deploy/.env`:

```env
BOT_PROVIDER=selfhosted
SELFBOT_URL=http://selfbot:8080
SELFBOT_TOKEN=              # optional; must match the worker's SELFBOT_TOKEN
```

Then bring the stack up — the `selfbot` service is defined in
`deploy/docker-compose.yml`. Invite the bot to any meeting link as usual; in
mock mode it completes in ~10s with the demo transcript and a Sonnet 5 summary,
proving the path before Phase 2's real browser bot lands.

## Run locally (without Docker)

```bash
cd selfbot
pip install -r requirements.txt
SELFBOT_DEMO_WAV=../backend/tests/data/demo_meeting.wav \
  uvicorn worker:app --port 8080
```
