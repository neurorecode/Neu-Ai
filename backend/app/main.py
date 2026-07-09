import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine, run_sqlite_auto_migrations
from .routers import chat, meetings
from .services.jobs import recover_stale_jobs, worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_sqlite_auto_migrations()
    recover_stale_jobs()

    stop_event = asyncio.Event()
    worker = asyncio.create_task(worker_loop(stop_event))
    yield
    stop_event.set()
    await worker


app = FastAPI(
    title="Neu AI",
    description=(
        "AI meeting assistant for Tamil, English & Tanglish — "
        "transcription, bilingual summaries, action items, and meeting chat."
    ),
    version="0.2.0",
    lifespan=lifespan,
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
    from .services.audio import ffmpeg_available

    return {
        "status": "ok",
        "stt_provider": settings.stt_provider,
        "llm_configured": bool(settings.anthropic_api_key),
        "ffmpeg": ffmpeg_available(),
        "diarization": settings.diarization,
    }
