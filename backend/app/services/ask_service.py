"""Cross-meeting intelligence: answer a question across ALL of a user's
meetings, not just one.

Retrieval is deliberately dependency-free (no embeddings service): we score
meetings by keyword overlap over their transcript + summary, take the most
relevant handful, and hand their summaries + matching snippets to Claude with
instructions to cite which meeting each fact came from. For a single team's
volume this is fast, cheap, and good enough; semantic embeddings are a natural
future upgrade.
"""

import re
from datetime import datetime

from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Meeting, TranscriptSegment

# Tiny stopword set so keyword scoring focuses on meaningful terms. Tamil-script
# words are always kept (they carry meaning and rarely appear here).
_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "with", "what", "when", "who",
    "did", "does", "our", "you", "your", "about", "from", "this", "that", "have",
    "has", "had", "all", "any", "can", "could", "would", "should", "will", "list",
    "show", "tell", "give", "summarize", "summary", "meeting", "meetings", "neu",
}

MAX_MEETINGS = 6
SNIPPETS_PER_MEETING = 6
SNIPPET_CHARS = 240

SYSTEM_TEMPLATE = """You are Neu, an AI meeting assistant for Tamil, English and Tanglish \
(Tamil-English code-mixed) meetings — similar to Fireflies or Avoma, built for Tamil speakers.

You are answering a question that spans MULTIPLE meetings. Below is context drawn from the \
user's most relevant meetings: each block has the meeting title, date, its summary, and \
selected transcript snippets with timestamps.

Rules:
- Answer in the SAME language style the user writes in: English question → English answer; \
Tamil script → Tamil script; Tanglish → Tanglish.
- Synthesize across meetings. When you state a fact, cite the meeting it came from by title \
and date, e.g. "(Sales Team Stand up call, 11 Jul)".
- For "action items" / "decisions" questions, gather them from every relevant meeting and \
group clearly.
- Ground every answer in the context. If the context doesn't contain the answer, say so \
honestly rather than guessing.
- Be concise and well-structured (use short bullet lists where it helps).

CONTEXT:
{context}"""


def _keywords(question: str) -> list[str]:
    tokens = re.findall(r"[\w஀-௿]+", question.lower())
    return [t for t in tokens if t not in _STOPWORDS and (len(t) >= 3 or _is_tamil(t))]


def _is_tamil(text: str) -> bool:
    return any("஀" <= ch <= "௿" for ch in text)


def _rank_meetings(db: Session, workspace_ids: list[str], keywords: list[str]) -> list[Meeting]:
    """Return the most relevant completed meetings for the keywords (or the most
    recent ones when there are no usable keywords / no matches)."""
    base = (
        db.query(Meeting)
        .filter(Meeting.workspace_id.in_(workspace_ids), Meeting.status == "completed")
    )
    if not keywords:
        return base.order_by(Meeting.created_at.desc()).limit(MAX_MEETINGS).all()

    scores: dict[str, int] = {}
    for kw in keywords:
        pattern = f"%{kw}%"
        # Segment matches (the bulk of the signal)
        seg_hits = (
            db.query(TranscriptSegment.meeting_id)
            .join(Meeting, TranscriptSegment.meeting_id == Meeting.id)
            .filter(
                Meeting.workspace_id.in_(workspace_ids),
                Meeting.status == "completed",
                TranscriptSegment.text.ilike(pattern),
            )
            .limit(200)
            .all()
        )
        for (mid,) in seg_hits:
            scores[mid] = scores.get(mid, 0) + 1
        # Title matches weigh a bit more
        for (mid,) in (
            base.with_entities(Meeting.id).filter(Meeting.title.ilike(pattern)).all()
        ):
            scores[mid] = scores.get(mid, 0) + 3

    if not scores:
        return base.order_by(Meeting.created_at.desc()).limit(MAX_MEETINGS).all()

    ranked_ids = sorted(scores, key=lambda m: scores[m], reverse=True)[:MAX_MEETINGS]
    meetings = base.filter(Meeting.id.in_(ranked_ids)).all()
    # Preserve score order
    order = {mid: i for i, mid in enumerate(ranked_ids)}
    meetings.sort(key=lambda m: order.get(m.id, 999))
    return meetings


def _summary_block(meeting: Meeting) -> str:
    s = meeting.summary
    if not s:
        return ""
    parts = []
    if s.overview_en:
        parts.append(f"Overview: {s.overview_en}")
    if s.decisions:
        parts.append("Decisions: " + "; ".join(str(d) for d in s.decisions))
    if s.action_items:
        items = "; ".join(
            f"{a.get('task','')} ({a.get('owner','?')}, {a.get('due','—')})"
            for a in s.action_items
        )
        parts.append(f"Action items: {items}")
    return "\n".join(parts)


def _snippets(meeting: Meeting, keywords: list[str]) -> list[TranscriptSegment]:
    segs = meeting.segments
    if keywords:
        matched = [
            seg for seg in segs
            if any(kw in (seg.text or "").lower() for kw in keywords)
        ]
        if matched:
            return matched[:SNIPPETS_PER_MEETING]
    return segs[:SNIPPETS_PER_MEETING]


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def build_context(meetings: list[Meeting], keywords: list[str]) -> tuple[str, list[dict]]:
    """Return (context_text, sources) for the given meetings."""
    blocks, sources = [], []
    for meeting in meetings:
        date = meeting.created_at.strftime("%d %b %Y") if meeting.created_at else ""
        lines = [f"### MEETING: {meeting.title} — {date}"]
        summary = _summary_block(meeting)
        if summary:
            lines.append(summary)
        snippet_lines = [
            f"[{_fmt_time(seg.start)}] {(seg.speaker + ': ') if seg.speaker else ''}"
            f"{(seg.text or '')[:SNIPPET_CHARS]}"
            for seg in _snippets(meeting, keywords)
        ]
        if snippet_lines:
            lines.append("Snippets:\n" + "\n".join(snippet_lines))
        blocks.append("\n".join(lines))
        sources.append(
            {"meeting_id": meeting.id, "title": meeting.title, "date": date}
        )
    return "\n\n".join(blocks), sources


async def ask_across_meetings(
    db: Session, workspace_ids: list[str], question: str
) -> tuple[str, list[dict]]:
    keywords = _keywords(question)
    meetings = _rank_meetings(db, workspace_ids, keywords)

    if not meetings:
        return (
            "I couldn't find any completed meetings to search yet. Once you have a few "
            "meetings transcribed, ask me anything across all of them.",
            [],
        )

    context, sources = build_context(meetings, keywords)

    if not settings.anthropic_api_key:
        return (
            "Cross-meeting Ask is unavailable because ANTHROPIC_API_KEY is not configured.",
            sources,
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = SYSTEM_TEMPLATE.format(context=context)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": question}],
    )
    answer = next((b.text for b in response.content if b.type == "text"), "")
    return answer, sources
