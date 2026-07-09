# Neu AI — நீ

**An AI meeting assistant like Fireflies / Avoma, built exclusively for Tamil, English, and Tanglish (Tamil-English code-mixed) meetings.**

Upload a recording or record live from the browser. Neu transcribes the audio, tags every utterance as **தமிழ் / English / Tanglish**, generates a **bilingual summary** (English + Tamil) with action items and decisions, and lets you **chat with the meeting** in whichever of the three languages you prefer.

## Features

| Feature | Details |
|---|---|
| 🎙️ Ingest | Upload audio/video (`wav, mp3, m4a, mp4, webm, ogg, flac, aac`) or record live from the browser mic |
| 📝 Transcription | Pluggable STT: **Sarvam AI** (best for Tamil & code-mixed speech), **OpenAI Whisper**, **local faster-whisper**, or a keyless **mock** demo provider |
| 🌐 Language tagging | Every transcript segment is classified as Tamil (script-based), English, or Tanglish (romanized-Tamil / code-mixed detection) |
| 🧠 AI summary | Claude generates a bilingual overview (English + தமிழ்), key points, action items (task / owner / due), decisions, topics, and tone |
| 🎛️ Audio pipeline | ffmpeg normalization (16 kHz mono WAV), long recordings chunked & stitched, retries with backoff, live progress (% + stage) |
| 🧵 Job queue | Persistent DB-backed queue — interrupted jobs resume after a crash/restart |
| 👤 Speakers | Optional pyannote diarization; rename speakers across a meeting in the UI |
| ✏️ Editing | Fix mis-transcribed segments inline (language re-detected), then re-summarize |
| 🔐 Auth & teams | Google sign-in (JWT sessions), workspaces with owner/member/viewer roles, email invites |
| 🔗 Sharing | Public view-only share links for any meeting (revocable) |
| ▶️ Playback | Audio player synced to the transcript — click a timestamp to play, follow-along highlight |
| 🚀 Deploy | One-command Docker Compose stack (Caddy auto-HTTPS + Postgres 16 + nightly backups) — see [DEPLOY.md](DEPLOY.md) |
| 💬 Ask Neu | Chat with any meeting — ask in Tamil, English, or Tanglish and get an answer in the same language, grounded in the transcript with timestamps |
| 🔍 Search | Full-text search across all meetings in any of the three languages/scripts |

## Architecture

```
frontend/  React + Vite + TypeScript  (dashboard, transcript, summary, chat)
backend/   FastAPI + SQLAlchemy (SQLite)
  app/services/stt/        pluggable speech-to-text providers
  app/services/language.py Tamil / English / Tanglish classifier
  app/services/summarizer.py  Claude bilingual summarization (structured output)
  app/services/chat_service.py  Claude "chat with your meeting" (prompt-cached transcript)
  app/services/pipeline.py  background job: transcribe → tag → summarize
```

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # then edit .env
uvicorn app.main:app --reload --port 8000
```

The default configuration (`STT_PROVIDER=mock`, no keys) works out of the box:
uploading **any** audio file produces a realistic demo Tanglish stand-up transcript
so you can try the whole flow immediately. Add an `ANTHROPIC_API_KEY` to enable
real AI summaries and chat.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the backend on port 8000.

## Configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Enables Claude summaries, action items, and meeting chat. Get one at [platform.claude.com](https://platform.claude.com) |
| `ANTHROPIC_MODEL` | Defaults to `claude-opus-4-8` |
| `STT_PROVIDER` | `mock` (default, keyless demo) · `sarvam` · `openai` · `local` |
| `SARVAM_API_KEY` | For `sarvam` — [Sarvam AI](https://www.sarvam.ai) `saarika` model, the strongest choice for Tamil + Tanglish audio |
| `OPENAI_API_KEY` | For `openai` — Whisper API |
| `LOCAL_WHISPER_MODEL` | For `local` — faster-whisper model size (`pip install faster-whisper` required) |
| `DIARIZATION` | `none` (default) or `pyannote` — speaker labels on real recordings (`pip install pyannote.audio` + `HF_TOKEN`) |
| `LANGUAGE_LLM_FALLBACK` | Re-check ambiguous segments with Claude (default `true`, needs the Anthropic key) |

`ffmpeg` must be installed for real audio processing (`apt install ffmpeg` / `brew install ffmpeg`).

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```

Includes a 100-utterance Tamil/English/Tanglish eval set gating classifier
accuracy at ≥90%, plus audio, job-queue crash-recovery, and end-to-end API tests.

## How Tamil / English / Tanglish detection works

`backend/app/services/language.py` classifies each transcript segment:

1. **Tamil script present + Latin present → Tanglish** (code-mixed)
2. **Tamil script only → Tamil**
3. **Latin only** → checked against a curated lexicon of ~150 high-frequency
   romanized Tamil words and particles (`seri`, `panren`, `irukku`, `venum`,
   `machan`, `da`, `nu`, …). Strong or multiple matches → **Tanglish**,
   otherwise **English**.

Meeting-level language is rolled up from segment labels, and the summary shows
a per-language percentage breakdown.

## API overview

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/meetings` | Upload audio (multipart: `title`, `file`) — starts the pipeline |
| `GET` | `/api/meetings` | List meetings |
| `GET` | `/api/meetings/{id}` | Meeting detail: segments + summary |
| `POST` | `/api/meetings/{id}/reprocess` | Re-run transcription + summary |
| `DELETE` | `/api/meetings/{id}` | Delete meeting + audio |
| `GET` | `/api/meetings/search?q=` | Full-text search |
| `GET/POST` | `/api/meetings/{id}/chat` | Chat history / ask a question |
| `GET` | `/api/health` | Health + configured providers |

## Roadmap

- **Meeting-bot auto-join** (Zoom / Google Meet / Teams) via a bot provider such as
  [Recall.ai](https://recall.ai) — the pipeline is already provider-agnostic, the
  bot simply needs to deliver audio to `POST /api/meetings`.
- **Speaker diarization** for non-mock providers (pyannote or provider-native
  diarization), so real recordings get speaker labels like the demo does.
- **Live (streaming) transcription** during in-progress meetings.
- Calendar integration for automatic recording scheduling.
