"""Structured log context: run_id, job_id, source_name, artifact_id (EPIC 10)."""

import logging
from contextvars import ContextVar
from typing import Any

_log_context: ContextVar[dict[str, Any]] = ContextVar(
    "log_context",
    default={},
)


def get_log_context() -> dict[str, Any]:
    """Return current contextual identifiers for structured logging."""
    return dict(_log_context.get())


def with_log_context(
    *,
    run_id: str | None = None,
    job_id: str | None = None,
    source_name: str | None = None,
    artifact_id: str | None = None,
    task_name: str | None = None,
) -> dict[str, Any]:
    """
    Update contextual identifiers. Returns dict suitable for logging.

    Usage:
        ctx = with_log_context(run_id=run_id, job_id=job_id)
        logger.info("Processing", extra=ctx)
    """
    ctx = dict(_log_context.get())
    if run_id is not None:
        ctx["run_id"] = run_id
    if job_id is not None:
        ctx["job_id"] = job_id
    if source_name is not None:
        ctx["source_name"] = source_name
    if artifact_id is not None:
        ctx["artifact_id"] = artifact_id
    if task_name is not None:
        ctx["task_name"] = task_name
    _log_context.set(ctx)
    return ctx


def _build_extra(extra: dict | None) -> dict:
    """Merge log context into extra so formatters pick up structured fields."""
    base = get_log_context()
    if extra:
        base.update(extra)
    return base


class StructuredAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter that injects run_id, job_id, source_name, artifact_id into
    every log record. Use with standard logging; works with grep-friendly and
    JSON formatters.
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra") or {}
        extra.update(get_log_context())
        kwargs["extra"] = extra
        return msg, kwargs


def get_structured_logger(name: str) -> StructuredAdapter:
    """Get a logger that automatically includes contextual identifiers."""
    return StructuredAdapter(logging.getLogger(name), {})
