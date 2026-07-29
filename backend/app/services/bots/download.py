"""Download a bot recording to local storage so the normal pipeline can run.

Handles three shapes of `audio_url`:
  * pre-signed HTTP(S) URLs (Recall, or a cross-container self-hosted worker),
  * file:// URLs (mock/tests), and
  * bare local filesystem paths (a self-hosted worker sharing the upload volume)."""

from pathlib import Path
from urllib.parse import urlparse

import httpx

from ...config import settings


async def download_recording(meeting_id: str, audio_url: str, ext: str) -> str:
    dest = Path(settings.upload_dir) / f"{meeting_id}{ext}"

    parsed = urlparse(audio_url)
    # A local file: explicit file:// URL, or a bare path that exists on disk
    # (worker shares the upload volume — no copy over the network needed).
    if parsed.scheme == "file" or (parsed.scheme in ("", None) and Path(audio_url).exists()):
        src = Path(parsed.path) if parsed.scheme == "file" else Path(audio_url)
        if src.resolve() != dest.resolve():
            dest.write_bytes(src.read_bytes())
        return str(dest)

    async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
        async with client.stream("GET", audio_url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as out:
                async for chunk in resp.aiter_bytes(1024 * 256):
                    out.write(chunk)
    return str(dest)
