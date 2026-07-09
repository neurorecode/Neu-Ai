"""Meeting summarization via the Claude API.

Produces a bilingual (English + Tamil) summary with key points, action items,
decisions, and topics. Handles Tamil / English / Tanglish transcripts natively —
Claude reads code-mixed text directly, no pre-translation step.
"""

import json

from anthropic import AsyncAnthropic

from ..config import settings

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "overview_en": {
            "type": "string",
            "description": "3-5 sentence overview of the meeting, in English.",
        },
        "overview_ta": {
            "type": "string",
            "description": "The same overview written in Tamil script (தமிழ்).",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Most important discussion points, in the meeting's own language style.",
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "owner": {"type": "string", "description": "Person responsible, or 'Unassigned'."},
                    "due": {"type": "string", "description": "Deadline if mentioned, else 'Not specified'."},
                },
                "required": ["task", "owner", "due"],
                "additionalProperties": False,
            },
        },
        "decisions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete decisions that were made.",
        },
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short topic tags (2-4 words each).",
        },
        "sentiment": {
            "type": "string",
            "description": "One sentence on the overall tone/energy of the meeting.",
        },
    },
    "required": [
        "overview_en",
        "overview_ta",
        "key_points",
        "action_items",
        "decisions",
        "topics",
        "sentiment",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the summarization engine of an AI meeting assistant built \
specifically for Tamil, English, and Tanglish (Tamil-English code-mixed) meetings.

You will receive a meeting transcript. Speakers may switch freely between English, \
Tamil script (தமிழ்), and romanized Tamil (Tanglish, e.g. "deploy panniyacha?", \
"seri, Friday kulla mudichiduven"). Understand all three fluently.

Rules:
- Extract action items with the owner's name whenever a speaker is identified.
- overview_en must be natural English; overview_ta must be natural Tamil script \
(not transliterated English).
- key_points and decisions should preserve important Tamil/Tanglish phrasing where \
it carries meaning, with a short English gloss in parentheses when helpful.
- Never invent facts that are not in the transcript."""


def _format_transcript(segments) -> str:
    lines = []
    for seg in segments:
        speaker = seg.speaker or "Speaker"
        lines.append(f"[{seg.start:.0f}s] {speaker}: {seg.text}")
    return "\n".join(lines)


def _preferences_note(summary_language: str, vocabulary: list | None) -> str:
    notes = []
    if summary_language == "en":
        notes.append(
            "Workspace preference: write key_points, decisions, and action items in English "
            "(overview_ta must still be provided in Tamil)."
        )
    elif summary_language == "ta":
        notes.append(
            "Workspace preference: write key_points, decisions, and action items in Tamil script "
            "(overview_en must still be provided in English)."
        )
    if vocabulary:
        terms = ", ".join(str(v) for v in vocabulary[:200])
        notes.append(
            "Custom vocabulary — these are correct spellings of names/terms used by this team; "
            f"prefer them when the transcript has near-matches: {terms}"
        )
    return ("\n\n" + "\n".join(notes)) if notes else ""


async def summarize_meeting(
    segments, summary_language: str = "both", vocabulary: list | None = None
) -> dict:
    """Return the summary dict matching SUMMARY_SCHEMA."""
    if not settings.anthropic_api_key:
        return {
            "overview_en": (
                "Summary unavailable: ANTHROPIC_API_KEY is not configured. "
                "Add your key to .env to enable AI summaries, action items, and chat."
            ),
            "overview_ta": (
                "ANTHROPIC_API_KEY அமைக்கப்படவில்லை. AI சுருக்கம் மற்றும் அரட்டையை "
                "இயக்க .env கோப்பில் உங்கள் key-ஐ சேர்க்கவும்."
            ),
            "key_points": [],
            "action_items": [],
            "decisions": [],
            "topics": [],
            "sentiment": None,
        }

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    transcript = _format_transcript(segments)

    async with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=8192,
        system=SYSTEM_PROMPT + _preferences_note(summary_language, vocabulary),
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"Summarize this meeting transcript:\n\n{transcript}",
            }
        ],
    ) as stream:
        response = await stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
