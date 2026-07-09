"""Keyless demo provider: returns a realistic Tanglish stand-up transcript so
the full pipeline (language tagging, summary, chat) can be exercised without
any STT credentials."""

import asyncio

from .base import ProgressCallback, STTProvider, TranscriptResult, TranscriptSegmentData

DEMO_SEGMENTS = [
    (0.0, 6.5, "Priya", "Vanakkam everyone, let's start the sprint stand-up. Ellarum ready ah?"),
    (6.5, 14.0, "Karthik", "Yes Priya. Naan payment gateway integration mudichitten, testing la irukku ippo."),
    (14.0, 22.0, "Priya", "Super Karthik. Staging la deploy panniyacha? QA team ku access venum."),
    (22.0, 30.5, "Karthik", "Innum illa, today evening deploy pannuren. Oru small config issue irundhuchu, fixed now."),
    (30.5, 39.0, "Divya", "என் பக்கம் இருந்து UI redesign முடிந்தது. Figma link team channel ல share பண்ணிட்டேன்."),
    (39.0, 47.5, "Priya", "Great. Divya, can you also handle the Tamil font rendering bug? Mobile la text overlap aaguthu."),
    (47.5, 54.0, "Divya", "Seri, I'll take it. Friday kulla fix panniduven."),
    (54.0, 63.0, "Arjun", "One blocker from my side — analytics API rate limit hit aaguthu production la. Vendor kitta pesanum."),
    (63.0, 72.0, "Priya", "Okay, adhu critical. Arjun, you set up a call with the vendor tomorrow. Naanum join panren."),
    (72.0, 80.0, "Arjun", "Sure, will send the invite. Also we should decide on the caching layer — Redis ah illa in-memory ah?"),
    (80.0, 89.5, "Karthik", "Redis better da, multi-instance scale aagum bodhu in-memory work aagadhu."),
    (89.5, 96.0, "Priya", "Agreed, let's go with Redis. Decision final. Vera edhavadhu irukka?"),
    (96.0, 102.0, "Divya", "Illa, that's all from me. Nandri!"),
    (102.0, 108.0, "Priya", "Okay team, nalla velai. Same time tomorrow. Bye everyone!"),
]


class MockSTT(STTProvider):
    async def transcribe(
        self, audio_path: str, on_progress: ProgressCallback | None = None
    ) -> TranscriptResult:
        for i in range(3):  # simulate processing latency with progress
            await asyncio.sleep(0.5)
            if on_progress:
                on_progress((i + 1) / 3)
        segments = [
            TranscriptSegmentData(start=s, end=e, speaker=spk, text=txt)
            for s, e, spk, txt in DEMO_SEGMENTS
        ]
        return TranscriptResult(segments=segments, duration_seconds=DEMO_SEGMENTS[-1][1])
