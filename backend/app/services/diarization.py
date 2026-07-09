"""Optional speaker diarization via pyannote.audio.

Off by default (torch is a heavy dependency and the pyannote models require a
Hugging Face token with gated-model access). Enable with:

    pip install pyannote.audio
    DIARIZATION=pyannote
    HF_TOKEN=hf_...

Providers that already return speaker labels (e.g. the mock provider) skip
this step. Without diarization, meetings still work — segments just have no
speaker labels until renamed manually in the UI.
"""

import asyncio
import logging

from ..config import settings

logger = logging.getLogger("neu.diarization")

_pipeline = None


def diarization_enabled() -> bool:
    if settings.diarization.lower() != "pyannote":
        return False
    if not settings.hf_token:
        logger.warning("DIARIZATION=pyannote but HF_TOKEN is not set — skipping diarization")
        return False
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        logger.warning("DIARIZATION=pyannote but pyannote.audio is not installed — skipping")
        return False
    return True


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from pyannote.audio import Pipeline

        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=settings.hf_token
        )
    return _pipeline


def _diarize_sync(wav_path: str) -> list[tuple[float, float, str]]:
    """Return (start, end, speaker_key) turns."""
    pipeline = _get_pipeline()
    annotation = pipeline(wav_path)
    return [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]


def assign_speakers_from_turns(segments, turns, *, relabel: bool = True) -> None:
    """Label transcript segments in place from (start, end, speaker) turns.

    Each segment gets the speaker whose turns overlap it most. When relabel is
    True, opaque diarization keys are mapped to 'Speaker 1/2/…' in order of
    first appearance; when False (e.g. Recall gives real participant names),
    the turn labels are used verbatim.
    """
    if not turns:
        return

    label_map: dict[str, str] = {}

    def display_name(key: str) -> str:
        if not relabel:
            return key
        if key not in label_map:
            label_map[key] = f"Speaker {len(label_map) + 1}"
        return label_map[key]

    for seg in segments:
        overlaps: dict[str, float] = {}
        for t_start, t_end, speaker in turns:
            overlap = min(seg.end, t_end) - max(seg.start, t_start)
            if overlap > 0:
                overlaps[speaker] = overlaps.get(speaker, 0.0) + overlap
        if overlaps:
            best = max(overlaps, key=overlaps.get)
            seg.speaker = display_name(best)


async def apply_diarization(wav_path: str, segments) -> None:
    """Run pyannote diarization and label segments with 'Speaker N'."""
    turns = await asyncio.to_thread(_diarize_sync, wav_path)
    assign_speakers_from_turns(segments, turns, relabel=True)
