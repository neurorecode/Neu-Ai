from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start: float
    end: float
    speaker: str | None
    text: str
    language: str | None


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    overview_en: str | None
    overview_ta: str | None
    key_points: list | None
    action_items: list | None
    decisions: list | None
    topics: list | None
    sentiment: str | None
    language_breakdown: dict | None


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    error: str | None
    language: str | None
    duration_seconds: float | None
    progress: int
    stage: str | None
    source: str
    has_audio: bool
    created_at: datetime


class MeetingDetail(MeetingOut):
    segments: list[SegmentOut]
    summary: SummaryOut | None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str


class SegmentUpdate(BaseModel):
    text: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    picture: str | None


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    user: UserOut


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    summary_language: str
    custom_vocabulary: list | None
    role: str | None = None  # the requesting user's role, filled by the router


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    summary_language: str | None = None
    custom_vocabulary: list[str] | None = None


class InviteCreate(BaseModel):
    email: str
    role: str = "member"


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    token: str
    accepted_at: datetime | None


class MemberRoleUpdate(BaseModel):
    role: str


class ShareOut(BaseModel):
    share_token: str | None


class InviteBotRequest(BaseModel):
    meeting_url: str
    title: str | None = None
    workspace_id: str | None = None


class BotStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    provider: str
    meeting_url: str
    error: str | None


class SpeakerRename(BaseModel):
    from_name: str
    to_name: str


class SearchHit(BaseModel):
    meeting_id: str
    meeting_title: str
    segment_id: str | None
    snippet: str
    start: float | None


class AskRequest(BaseModel):
    question: str
    workspace_id: str | None = None


class AskSource(BaseModel):
    meeting_id: str
    title: str
    date: str


class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource]
