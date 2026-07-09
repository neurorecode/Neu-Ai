from ...config import settings
from .base import BotProvider, BotRecording, BotStatus, SpeakerTurn


def get_bot_provider() -> BotProvider:
    provider = settings.bot_provider.lower()
    if provider == "recall":
        from .recall import RecallBotProvider

        return RecallBotProvider(api_key=settings.recall_api_key, region=settings.recall_region)
    from .mock import MockBotProvider

    return MockBotProvider()


def bots_enabled() -> bool:
    """True when a real meeting-bot provider is configured."""
    return settings.bot_provider.lower() == "recall" and bool(settings.recall_api_key)


__all__ = ["get_bot_provider", "bots_enabled", "BotProvider", "BotRecording", "BotStatus", "SpeakerTurn"]
