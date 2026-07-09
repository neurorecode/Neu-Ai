from ...config import settings
from .base import STTProvider, TranscriptResult, TranscriptSegmentData


def get_stt_provider() -> STTProvider:
    provider = settings.stt_provider.lower()
    if provider == "sarvam":
        from .sarvam import SarvamSTT

        return SarvamSTT(api_key=settings.sarvam_api_key)
    if provider == "openai":
        from .openai_whisper import OpenAIWhisperSTT

        return OpenAIWhisperSTT(api_key=settings.openai_api_key)
    if provider == "local":
        from .whisper_local import LocalWhisperSTT

        return LocalWhisperSTT(model_size=settings.local_whisper_model)
    from .mock import MockSTT

    return MockSTT()


__all__ = ["get_stt_provider", "STTProvider", "TranscriptResult", "TranscriptSegmentData"]
