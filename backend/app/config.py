from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    stt_provider: str = "mock"  # mock | sarvam | openai | local
    sarvam_api_key: str = ""
    openai_api_key: str = ""
    local_whisper_model: str = "small"

    # Speaker diarization: none | pyannote (needs pyannote.audio + HF_TOKEN)
    diarization: str = "none"
    hf_token: str = ""

    # Use Claude to re-classify segments the heuristic finds ambiguous
    language_llm_fallback: bool = True

    # ---- Meeting bot (auto-join Meet/Zoom/Teams) ----
    # none | recall (Recall.ai — one API for all three platforms)
    bot_provider: str = "none"
    recall_api_key: str = ""
    recall_region: str = "us-west-2"
    bot_name: str = "Neu AI Notetaker"
    # Shared secret in the webhook path so only Recall can post to it
    webhook_secret: str = "changeme-webhook-secret"

    # ---- Email recap (SMTP) ----
    # When smtp_host is empty, recaps are logged to the console instead of sent.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Neu AI <noreply@localhost>"
    smtp_starttls: bool = True

    # STT chunking (seconds). Sarvam's sync endpoint caps around 30s of audio;
    # Whisper API caps at 25 MB (~13 min of 16kHz mono WAV).
    sarvam_chunk_seconds: float = 29.0
    openai_chunk_seconds: float = 600.0

    database_url: str = "sqlite:///./data/neu.db"
    upload_dir: str = "./data/uploads"

    # ---- Audio retention (disk hygiene) ----
    # Delete original recordings older than this many days, keeping the
    # transcript + summary forever (those are tiny). 0 = keep audio forever.
    # The normalized .norm.wav working file is always cleaned up right after
    # transcription regardless of this setting.
    audio_retention_days: int = 0
    # How often the retention sweep runs, in hours.
    retention_sweep_hours: float = 6.0

    # ---- Auth (Google sign-in) ----
    # When google_client_id is empty, the app runs in single-user dev mode:
    # every request is auto-authenticated as dev@localhost.
    google_client_id: str = ""
    google_client_secret: str = ""
    secret_key: str = "dev-insecure-secret-change-me"
    backend_url: str = "http://localhost:8000"   # public URL of the API (OAuth redirect base)
    frontend_url: str = "http://localhost:5173"  # where to send the browser after login
    session_days: int = 14
    # Optional extra guard on top of Google's Internal-audience setting:
    # comma-separated email domains allowed to sign in (empty = allow all)
    auth_allowed_email_domains: str = ""


settings = Settings()

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
