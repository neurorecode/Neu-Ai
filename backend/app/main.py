import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine, run_sqlite_auto_migrations
from .routers import auth, bots, calendar, chat, meetings, workspaces
from .services.autojoin import autojoin_loop
from .services.bot_service import bot_poll_loop
from .services.jobs import recover_stale_jobs, worker_loop
from .services.retention import retention_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_sqlite_auto_migrations()
    recover_stale_jobs()

    stop_event = asyncio.Event()
    worker = asyncio.create_task(worker_loop(stop_event))
    autojoin = asyncio.create_task(autojoin_loop(stop_event))
    bot_poll = asyncio.create_task(bot_poll_loop(stop_event))
    retention = asyncio.create_task(retention_loop(stop_event))
    yield
    stop_event.set()
    await worker
    await autojoin
    await bot_poll
    await retention


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

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(workspaces.accept_router)
app.include_router(meetings.router)
app.include_router(meetings.shared_router)
app.include_router(bots.router)
app.include_router(bots.webhook_router)
app.include_router(calendar.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    from .services.audio import ffmpeg_available

    from .services.bots import bots_enabled

    return {
        "status": "ok",
        "stt_provider": settings.stt_provider,
        "llm_configured": bool(settings.anthropic_api_key),
        "ffmpeg": ffmpeg_available(),
        "diarization": settings.diarization,
        "bot_provider": settings.bot_provider if bots_enabled() else "none",
    }
