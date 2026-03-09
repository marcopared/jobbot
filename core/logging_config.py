import logging
from logging.config import dictConfig


def configure_logging(app_env: str = "dev", level: str = "INFO") -> None:
    """Configure process-wide logging for API and worker components."""
    normalized_level = (level or "INFO").upper()
    if normalized_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        normalized_level = "INFO"

    sqlalchemy_level = "INFO" if app_env == "dev" else "WARNING"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": normalized_level,
            },
            "loggers": {
                # Keep SQL logs visible but less noisy outside dev.
                "sqlalchemy.engine": {
                    "level": sqlalchemy_level,
                    "propagate": True,
                },
                # Let uvicorn/celery logs flow into the same formatter/handler.
                "uvicorn": {"propagate": True},
                "uvicorn.error": {"propagate": True},
                "uvicorn.access": {"propagate": True},
                "celery": {"propagate": True},
            },
        }
    )

