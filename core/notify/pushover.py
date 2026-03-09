import httpx

from apps.api.settings import Settings
from core.notify.base import BaseNotifier

settings = Settings()


class PushoverNotifier(BaseNotifier):
    def send(self, title: str, message: str, url: str | None = None) -> bool:
        payload = {
            "token": settings.pushover_token,
            "user": settings.pushover_user,
            "title": title,
            "message": message,
            "priority": 0,
        }
        if url:
            payload["url"] = url
            payload["url_title"] = "Open in JobBot"

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.pushover.net/1/messages.json",
                data=payload,
            )
            return response.status_code == 200
