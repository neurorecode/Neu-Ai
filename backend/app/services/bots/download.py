"""Download a bot recording to local storage so the normal pipeline can run.

Handles both real pre-signed HTTPS URLs (Recall) and file:// URLs (mock/tests)."""

from pathlib import Path
from urllib.parse import urlparse

import httpx

from ...config import settings


async def download_recording(meeting_id: str, audio_url: str, ext: str) -> str:
    dest = Path(settings.upload_dir) / f"{meeting_id}{ext}"

    parsed = urlparse(audio_url)
    if parsed.scheme == "file":
        src = Path(parsed.path)
        dest.write_bytes(src.read_bytes())
        return str(dest)

    async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
        async with client.stream("GET", audio_url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as out:
                async for chunk in resp.aiter_bytes(1024 * 256):
                    out.write(chunk)
    return str(dest)
