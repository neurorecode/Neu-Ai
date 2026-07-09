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

    # STT chunking (seconds). Sarvam's sync endpoint caps around 30s of audio;
    # Whisper API caps at 25 MB (~13 min of 16kHz mono WAV).
    sarvam_chunk_seconds: float = 29.0
    openai_chunk_seconds: float = 600.0

    database_url: str = "sqlite:///./data/neu.db"
    upload_dir: str = "./data/uploads"


settings = Settings()

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
