import httpx

from apps.api.settings import Settings
from core.notify.base import BaseNotifier

settings = Settings()


class NtfyNotifier(BaseNotifier):
    def send(self, title: str, message: str, url: str | None = None) -> bool:
        topic = settings.ntfy_topic_url
        if not topic:
            return False

        headers = {"Title": title}
        if url:
            headers["Click"] = url

        with httpx.Client(timeout=10.0) as client:
            response = client.post(topic, content=message.encode("utf-8"), headers=headers)
            return 200 <= response.status_code < 300
