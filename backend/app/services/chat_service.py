"""Chat with a meeting: answers questions about the transcript in whichever
language the user asks (Tamil, English, or Tanglish)."""

from anthropic import AsyncAnthropic

from ..config import settings
from .summarizer import _format_transcript

SYSTEM_TEMPLATE = """You are Neu, an AI meeting assistant for Tamil, English and Tanglish \
(Tamil-English code-mixed) meetings — similar to Fireflies or Avoma, but built for \
Tamil speakers.

You are answering questions about ONE specific meeting. The full transcript is below. \
Speakers may mix English, Tamil script, and romanized Tamil freely.

Rules:
- Answer in the SAME language style the user writes in: English question → English answer; \
Tamil script → Tamil script; Tanglish → Tanglish.
- Ground every answer in the transcript. Quote short snippets (with the timestamp) as evidence.
- If the transcript does not contain the answer, say so honestly.
- Keep answers concise and useful.

MEETING TITLE: {title}

TRANSCRIPT:
{transcript}"""


async def chat_about_meeting(meeting, history: list[dict], user_message: str) -> str:
    if not settings.anthropic_api_key:
        return (
            "Chat is unavailable because ANTHROPIC_API_KEY is not configured. "
            "Add your Anthropic API key to the backend .env file to enable it."
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = SYSTEM_TEMPLATE.format(
        title=meeting.title, transcript=_format_transcript(meeting.segments)
    )

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    )
    return next((b.text for b in response.content if b.type == "text"), "")
