from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, title: str, message: str, url: str | None = None) -> bool:
        """Send a notification and return success."""
        raise NotImplementedError
