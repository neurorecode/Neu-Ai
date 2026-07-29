from ...config import settings
from .base import BotProvider, BotRecording, BotStatus, SpeakerTurn


def get_bot_provider() -> BotProvider:
    provider = settings.bot_provider.lower()
    if provider == "recall":
        from .recall import RecallBotProvider

        return RecallBotProvider(api_key=settings.recall_api_key, region=settings.recall_region)
    if provider == "selfhosted":
        from .selfhosted import SelfHostedBotProvider

        return SelfHostedBotProvider(
            worker_url=settings.selfbot_url,
            token=settings.selfbot_token,
            timeout=settings.selfbot_timeout,
        )
    from .mock import MockBotProvider

    return MockBotProvider()


def bots_enabled() -> bool:
    """True when a real meeting-bot provider is configured."""
    provider = settings.bot_provider.lower()
    if provider == "recall":
        return bool(settings.recall_api_key)
    if provider == "selfhosted":
        return bool(settings.selfbot_url)
    return False


__all__ = ["get_bot_provider", "bots_enabled", "BotProvider", "BotRecording", "BotStatus", "SpeakerTurn"]
