import json
import logging
from logging.config import dictConfig


class StructuredFormatter(logging.Formatter):
    """Grep-friendly dev format: appends run_id= job_id= etc. from extra when present."""

    CONTEXT_KEYS = ("run_id", "job_id", "source_name", "artifact_id", "task_name")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        parts = [base]
        for k in self.CONTEXT_KEYS:
            v = getattr(record, k, None)
            if v is not None:
                parts.append(f"{k}={v}")
        if len(parts) > 1:
            return " ".join(parts)
        return base


class JsonFormatter(logging.Formatter):
    """JSON format for production (Datadog-compatible)."""

    def format(self, record: logging.LogRecord) -> str:
        d = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k in ("run_id", "job_id", "source_name", "artifact_id", "task_name"):
            v = getattr(record, k, None) or (getattr(record, "extra", {}) or {}).get(k)
            if v is not None:
                d[k] = str(v)
        if record.exc_info:
            d["exception"] = self.formatException(record.exc_info)
        return json.dumps(d)


def configure_logging(app_env: str = "dev", level: str = "INFO") -> None:
    """Configure process-wide logging for API and worker components."""
    normalized_level = (level or "INFO").upper()
    if normalized_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        normalized_level = "INFO"

    sqlalchemy_level = "INFO" if app_env == "dev" else "WARNING"

    use_json = app_env in ("prod", "production", "staging")
    formatter = "json" if use_json else "structured"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
                "structured": {
                    "()": "core.logging_config.StructuredFormatter",
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
                "json": {
                    "()": "core.logging_config.JsonFormatter",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
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

