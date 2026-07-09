# Neu AI — Product Roadmap

Goal: a fully functional AI meeting assistant (Fireflies/Avoma class) exclusively for
**Tamil, English, and Tanglish** meetings.

Each phase is independently shippable. A phase is "done" when its acceptance
criteria pass end-to-end.

---

## Phase 0 — MVP foundation ✅ (done)

- Upload / browser-mic recording ingestion
- Pluggable STT (mock, Sarvam, OpenAI Whisper, local faster-whisper)
- Tamil / English / Tanglish per-segment classifier
- Claude bilingual summary (overview EN+TA, key points, action items, decisions, topics)
- Chat-with-meeting (answers in the asker's language)
- Full-text search, React dashboard

---

## Phase 1 — Real audio pipeline (production-grade transcription) ✅ (done — Sarvam verified live: TTS→STT round-trip + 73s chunked pipeline)

*Make real recordings work as well as the demo does.*

**Requirements**
1. **Audio normalization**: convert any upload (webm/m4a/mp4/…) to 16 kHz mono WAV
   via ffmpeg before STT; reject/flag corrupt files; extract true duration.
2. **Sarvam integration hardened**: chunk long audio (>30 min) with overlap and
   stitch results; retries with backoff; per-chunk progress updates.
3. **Speaker diarization**: "Speaker 1 / Speaker 2" labels on real audio
   (pyannote.audio locally, or provider-native diarization), with UI rename
   ("Speaker 1 → Priya") persisted across the transcript.
4. **Job queue**: move from FastAPI BackgroundTasks to a persistent queue
   (RQ/arq + Redis, or a DB-backed worker) so jobs survive restarts; visible
   progress (% + stage) in the UI.
5. **Transcript editing**: fix mis-transcribed words in the UI; edits update
   search and can trigger re-summarization.
6. **Language-detection upgrade**: optional LLM fallback for ambiguous segments;
   accuracy eval set (100 labeled Tamil/English/Tanglish utterances) with a
   regression test.
7. **Automated tests**: pytest suite for pipeline, language detection, API.

**Acceptance criteria**
- A real 45-minute Tanglish meeting recording (m4a) uploads, transcribes with
  speaker labels, and summarizes without manual intervention.
- Killing the server mid-job and restarting resumes/retries the job.

**Needs from you**: a Sarvam AI key (or decision to use local Whisper), 1–2 real
Tamil/Tanglish recordings for testing.

---

## Phase 2 — Users, teams & durable storage

*From single-user demo to multi-user product.*

**Requirements**
1. **Authentication**: email + OTP or Google OAuth; JWT sessions.
2. **Workspaces/teams**: meetings belong to a workspace; invite teammates;
   roles (owner / member / viewer).
3. **Sharing**: share a meeting via link (view-only) or with specific teammates.
4. **Postgres + Alembic migrations** (replace SQLite for production; keep SQLite for dev).
5. **Object storage**: audio files to S3-compatible storage (or Supabase storage)
   instead of local disk; signed playback URLs.
6. **Audio playback in UI**: player synced to transcript — click a segment to jump.
7. **Settings page**: per-workspace STT provider, summary language preferences
   (EN-only / TA-only / bilingual), custom vocabulary list (names, org terms).

**Acceptance criteria**
- Two users in one workspace see the same meetings; a third user cannot.
- Deploying a fresh instance from scratch requires only env vars + migrations.

**Needs from you**: choice of auth (Google OAuth vs email OTP), hosting target
(Supabase/AWS/self-host) — this decides the storage/DB choices.

---

## Phase 3 — Meeting bot & calendar (the "Fireflies moment")

*Neu joins your meetings automatically.*

**Requirements**
1. **Bot provider integration** (Recall.ai recommended — one API for Zoom, Google
   Meet, Teams): create bot, join by meeting URL, receive recording + speaker
   timeline via webhook, feed into the existing pipeline.
2. **"Invite Neu" flow**: paste a meeting link → bot joins; bot status shown live
   (waiting / recording / left).
3. **Google Calendar integration**: OAuth connect; auto-detect meetings with
   video links; per-meeting or rule-based auto-join ("join all my external calls").
4. **Zoom cloud-recording import** as a no-bot alternative (Zoom OAuth app,
   pull recordings + Zoom's own speaker data).
5. **Post-meeting email recap**: bilingual summary + action items emailed to the
   organizer/participants.
6. **Webhook security**: signature verification, idempotent processing.

**Acceptance criteria**
- Schedule a Google Meet, Neu auto-joins from the calendar, and the finished
  meeting appears in the dashboard with transcript + summary within minutes of
  the call ending, plus a recap email.

**Needs from you**: Recall.ai account (paid, ~$0.5–1/hr of bot time), Google Cloud
OAuth credentials, choice of first platform (Meet vs Zoom vs Teams).

---

## Phase 4 — Live experience (real-time)

*See the transcript while the meeting is happening.*

**Requirements**
1. **Streaming STT**: WebSocket pipeline (Sarvam streaming API or local Whisper
   streaming) for live captions with live language tags.
2. **Live meeting view**: real-time transcript, running notes, "catch me up"
   button (Claude summarizes what's happened so far).
3. **Live bot audio**: Recall.ai real-time audio stream → streaming STT.
4. **In-meeting highlights**: mark a moment ("flag this") to pin it to the summary.

**Acceptance criteria**
- During a live call, captions appear < 3 s behind speech; "catch me up"
  returns a mid-meeting summary in < 10 s.

---

## Phase 5 — Conversation intelligence (the "Avoma layer")

*Insights across all your meetings.*

**Requirements**
1. **Semantic search / RAG**: embed transcripts (multilingual embedding model);
   "Ask Neu" across *all* meetings, not just one — with citations that deep-link
   to the exact moment.
2. **Analytics**: talk-time per speaker, language-mix trends, question counts,
   interruption/monologue detection, sentiment over time.
3. **Topic & keyword trackers**: define trackers ("pricing", "வாடிக்கையாளர்
   புகார்", competitor names) that get flagged across all meetings.
4. **Action-item hub**: cross-meeting action-item list with owner/status;
   push to Slack / Notion / task tools.
5. **Custom summary templates**: per meeting type (stand-up, sales call,
   customer interview) with type-specific extraction.
6. **Tanglish-aware embeddings eval**: verify retrieval quality on romanized
   Tamil queries; add transliteration normalization if needed.

**Acceptance criteria**
- "What did Karthik commit to across last week's meetings?" answered correctly
  with links; trackers fire on both Tamil-script and romanized mentions.

---

## Phase 6 — Production hardening & launch

**Requirements**
1. Docker Compose + one-command deploy; CI (tests, typecheck, build) on GitHub Actions.
2. Observability: structured logs, error tracking (Sentry), pipeline metrics.
3. Security & privacy: encryption at rest for audio/transcripts, meeting
   retention policies, delete-my-data, consent notice when the bot joins
   (announcement in Tamil + English).
4. Rate limiting, API keys for programmatic access, usage metering
   (foundation for billing if this becomes commercial).
5. Mobile-responsive UI polish; PWA for the recorder.
6. Cost controls: per-workspace STT/LLM usage caps and dashboards.

**Acceptance criteria**
- A stranger can deploy from the README in < 30 minutes; a week of real usage
  with zero data loss and predictable cost.

---

## Suggested order & decision points

| Phase | Unlocks | Blocking decisions/keys |
|---|---|---|
| 1 | Real recordings work | Sarvam key (recommended) or local Whisper |
| 2 | Multiple users | Auth method, hosting/DB target |
| 3 | Auto-join meetings | Recall.ai account, Google OAuth, first platform |
| 4 | Live captions | (builds on 3) |
| 5 | Cross-meeting intelligence | Embedding provider choice |
| 6 | Launch | Deploy target |

Phases 1 → 2 → 3 is the recommended critical path; 4 and 5 can be reordered
based on whether "live" or "insights" matters more to you.
