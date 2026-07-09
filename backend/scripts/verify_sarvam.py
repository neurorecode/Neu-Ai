"""One-command live verification of the Sarvam STT integration.

Usage (from backend/, with SARVAM_API_KEY in .env or the environment):

    python -m scripts.verify_sarvam                 # self-test via Sarvam TTS
    python -m scripts.verify_sarvam path/to/audio   # test with your own recording

Without an audio argument, the script synthesizes a Tamil+Tanglish sentence
using Sarvam's TTS (bulbul), then transcribes it back through the app's real
pipeline pieces (ffmpeg normalization -> chunked SarvamSTT -> language
tagging), so it exercises exactly what production uses.
"""

import asyncio
import base64
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.config import settings
from app.services.audio import ffmpeg_available, normalize_audio
from app.services.language import classify_segments
from app.services.stt.sarvam import SarvamSTT

TTS_URL = "https://api.sarvam.ai/text-to-speech"
TEST_TEXT = (
    "வணக்கம் அனைவருக்கும். இன்று நாம் புதிய திட்டம் பற்றி பேசலாம். "
    "Deploy panniyacha nu sollunga. அடுத்த வாரம் demo இருக்கு. நன்றி."
)


async def synthesize_test_audio() -> str:
    print("No audio file given — synthesizing Tamil test speech via Sarvam TTS…")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            TTS_URL,
            headers={
                "api-subscription-key": settings.sarvam_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": TEST_TEXT,
                "target_language_code": "ta-IN",
                "model": "bulbul:v2",
                "speaker": "anushka",
            },
        )
    resp.raise_for_status()
    audios = resp.json().get("audios") or []
    if not audios:
        raise SystemExit(f"TTS returned no audio: {resp.text[:300]}")
    path = Path(tempfile.mkdtemp(prefix="neu-sarvam-")) / "tts_test.wav"
    path.write_bytes(base64.b64decode(audios[0]))
    print(f"  TTS audio written to {path}")
    return str(path)


async def main() -> None:
    if not settings.sarvam_api_key:
        raise SystemExit("SARVAM_API_KEY is not set (backend/.env or environment).")
    if not ffmpeg_available():
        raise SystemExit("ffmpeg is required — install it first (apt/brew install ffmpeg).")

    audio_path = sys.argv[1] if len(sys.argv) > 1 else await synthesize_test_audio()

    print(f"Normalizing {audio_path} …")
    wav_path, duration = await normalize_audio(audio_path)
    print(f"  normalized to {wav_path} ({duration:.1f}s)")

    print("Transcribing via Sarvam saarika (chunked, with retries)…")
    stt = SarvamSTT(api_key=settings.sarvam_api_key)
    result = await stt.transcribe(wav_path, on_progress=lambda f: print(f"  progress {f:.0%}"))

    if not result.segments:
        raise SystemExit("FAIL: Sarvam returned no segments. Raw response shape may have changed.")

    labels, dominant, breakdown = await classify_segments([s.text for s in result.segments])

    print(f"\nOK — {len(result.segments)} segment(s), dominant language: {dominant}")
    print(f"Language breakdown: {json.dumps(breakdown, ensure_ascii=False)}\n")
    for seg, lang in zip(result.segments, labels):
        print(f"  [{seg.start:7.2f}s - {seg.end:7.2f}s] ({lang}) {seg.text}")

    if len(sys.argv) <= 1:
        print("\nExpected roughly: வணக்கம் அனைவருக்கும் / deploy panniyacha / demo இருக்கு …")
        print("If the transcript above matches the test sentence, the integration works.")


if __name__ == "__main__":
    asyncio.run(main())
