import uuid
from datetime import datetime, timedelta, timezone

ARCHIVE_AFTER_DAYS = 30

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    # Google profile-picture URLs can exceed 1KB — use unbounded Text so
    # Postgres (which enforces varchar limits, unlike SQLite) doesn't truncate.
    picture: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    # Google OAuth tokens for Calendar access (offline refresh token stored so
    # the background auto-join poller can read the user's calendar).
    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_token_expiry: Mapped[datetime | None] = mapped_column(nullable=True)
    google_scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Auto-join preference: none | video (join all calls with a video link)
    auto_join: Mapped[str] = mapped_column(String(10), default="none")

    memberships: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=_now)
    # Workspace preferences
    summary_language: Mapped[str] = mapped_column(String(10), default="both")  # en | ta | both
    custom_vocabulary: Mapped[list | None] = mapped_column(JSON, nullable=True)

    members: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    meetings: Mapped[list["Meeting"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    invites: Mapped[list["Invite"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


ROLES = ("owner", "member", "viewer")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(10), default="member")  # owner | member | viewer
    created_at: Mapped[datetime] = mapped_column(default=_now)

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(10), default="member")
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_id)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=_now)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="invites")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id"), index=True, nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # non-null enables the public view-only share link
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    # how the meeting entered the system: upload | bot (auto-joined a call)
    source: Mapped[str] = mapped_column(String(20), default="upload")
    # calendar event this meeting was auto-joined from (dedup for the poller)
    calendar_event_id: Mapped[str | None] = mapped_column(String(256), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    # uploaded -> transcribing -> summarizing -> completed | failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # dominant language of the meeting: tamil | english | tanglish | mixed
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # pipeline progress: 0-100 plus a human-readable stage description
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    workspace: Mapped[Workspace | None] = relationship(back_populates="meetings")
    bot: Mapped["MeetingBot | None"] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", uselist=False
    )
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="TranscriptSegment.start"
    )
    summary: Mapped["Summary | None"] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", uselist=False
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    @property
    def has_audio(self) -> bool:
        """Whether a playable recording still exists (may be purged by the
        retention policy while the transcript/summary are kept)."""
        return self.audio_path is not None


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
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    meeting: Mapped[Meeting] = relationship(back_populates="summary")


class MeetingBot(Base):
    """A dispatched meeting bot (Recall.ai) tied to a Meeting.

    Tracks the bot lifecycle and stores the speaker timeline the provider
    returns, so transcript segments can be labelled with real participant names.
    """

    __tablename__ = "meeting_bots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(20), default="recall")
    provider_bot_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    meeting_url: Mapped[str] = mapped_column(Text)
    # joining | recording | done | failed | left
    status: Mapped[str] = mapped_column(String(20), default="joining")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{start, end, speaker}, ...] captured from the provider once available
    speaker_timeline: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    meeting: Mapped[Meeting] = relationship(back_populates="bot")


class Task(Base):
    """A workspace task on the Kanban board.

    Tasks come from two sources: `meeting` (auto-extracted from a meeting's
    action items) and `manual` (created by a user). Status drives the board
    columns; done_at powers the 30-day auto-archive.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id"), index=True, nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # source meeting for auto-extracted tasks (null for manual tasks)
    meeting_id: Mapped[str | None] = mapped_column(
        ForeignKey("meetings.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # todo | doing | done  (Kanban columns)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)
    # meeting | manual
    source: Mapped[str] = mapped_column(String(20), default="manual")
    # set when moved to done; drives the 30-day archive
    done_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    @property
    def archived(self) -> bool:
        """Done tasks auto-hide from the board after 30 days (still searchable)."""
        if self.status != "done" or self.done_at is None:
            return False
        dt = self.done_at if self.done_at.tzinfo else self.done_at.replace(tzinfo=timezone.utc)
        return dt < datetime.now(timezone.utc) - timedelta(days=ARCHIVE_AFTER_DAYS)


class Job(Base):
    """Persistent work queue entry. Jobs survive process restarts: on startup
    any job left in 'running' (crashed mid-flight) is re-queued."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    # process (full pipeline) | summarize (summary only, keep transcript)
    type: Mapped[str] = mapped_column(String(20), default="process")
    # queued | running | done | failed
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"))
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    meeting: Mapped[Meeting] = relationship(back_populates="chat_messages")
