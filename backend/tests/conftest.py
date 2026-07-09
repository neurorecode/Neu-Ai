"""Test environment: isolated temp DB/uploads, mock STT, no LLM calls.

Environment variables are set before any app import so pydantic-settings
picks them up (env vars take precedence over .env)."""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="neu-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["STT_PROVIDER"] = "mock"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["LANGUAGE_LLM_FALLBACK"] = "false"
os.environ["DIARIZATION"] = "none"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    # Context manager runs the lifespan: schema creation, job recovery, worker.
    with TestClient(app) as c:
        yield c
