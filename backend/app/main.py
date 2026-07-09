from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import chat, meetings

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Neu AI",
    description=(
        "AI meeting assistant for Tamil, English & Tanglish — "
        "transcription, bilingual summaries, action items, and meeting chat."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "stt_provider": settings.stt_provider,
        "llm_configured": bool(settings.anthropic_api_key),
    }
