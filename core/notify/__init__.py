from apps.api.settings import Settings
from core.notify.base import BaseNotifier
from core.notify.ntfy import NtfyNotifier
from core.notify.pushover import PushoverNotifier


class NoopNotifier(BaseNotifier):
    def send(self, title: str, message: str, url: str | None = None) -> bool:
        return True


def get_notifier() -> BaseNotifier:
    settings = Settings()
    provider = settings.push_provider.lower()
    if provider == "pushover":
        return PushoverNotifier()
    if provider == "ntfy":
        return NtfyNotifier()
    return NoopNotifier()


__all__ = ["get_notifier", "BaseNotifier"]
