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


class SpeakerRename(BaseModel):
    from_name: str
    to_name: str


class SearchHit(BaseModel):
    meeting_id: str
    meeting_title: str
    segment_id: str | None
    snippet: str
    start: float | None
