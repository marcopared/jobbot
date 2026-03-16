"""Observability: structured logging, metrics, retries, failure visibility (EPIC 10)."""

from core.observability.context import get_log_context, log_context, with_log_context
from core.observability.metrics import get_metrics
from core.observability.failures import record_task_failure, get_recent_failures

__all__ = [
    "get_log_context",
    "log_context",
    "with_log_context",
    "get_metrics",
    "record_task_failure",
    "get_recent_failures",
]
