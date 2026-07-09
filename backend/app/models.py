import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    title: Mapped[str] = mapped_column(String(255))
    # uploaded -> transcribing -> summarizing -> completed | failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # dominant language of the meeting: tamil | english | tanglish | mixed
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="TranscriptSegment.start"
    )
    summary: Mapped["Summary | None"] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", uselist=False
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    speaker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    # tamil | english | tanglish
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="segments")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), unique=True)
    overview_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    overview_ta: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    action_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    decisions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="summary")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    meeting: Mapped[Meeting] = relationship(back_populates="chat_messages")
