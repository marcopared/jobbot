from apps.api.settings import Settings
from core.db.session import get_db

__all__ = ["get_db", "get_settings"]


def get_settings() -> Settings:
    """Return application settings."""
    return Settings()
