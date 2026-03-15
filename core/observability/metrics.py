"""Datadog-compatible metrics instrumentation (EPIC 10).

Sends to DogStatsD when DD_AGENT_HOST or STATSD_HOST is set; no-op otherwise.
Metric names use jobbot.* prefix for namespace.
"""

import os
import time
from typing import Any

_metrics_instance: Any = None


def _init_client() -> Any:
    """Lazy init DogStatsD or statsd client when host is configured."""
    global _metrics_instance
    if _metrics_instance is not None:
        return _metrics_instance
    host = os.environ.get("DD_AGENT_HOST") or os.environ.get("STATSD_HOST")
    port = int(os.environ.get("STATSD_PORT", "8125"))
    if not host:
        _metrics_instance = _NoopMetrics()
        return _metrics_instance
    try:
        from datadog import statsd

        statsd.init(host=host, port=port, namespace="jobbot")
        _metrics_instance = _DogStatsdMetrics(statsd)
        return _metrics_instance
    except ImportError:
        try:
            import statsd

            client = statsd.StatsClient(host=host, port=port, prefix="jobbot")
            _metrics_instance = _StatsdMetrics(client)
            return _metrics_instance
        except ImportError:
            _metrics_instance = _NoopMetrics()
            return _metrics_instance


def get_metrics():
    """Return metrics client (DogStatsD, statsd, or no-op)."""
    return _init_client()


class _NoopMetrics:
    """No-op metrics when statsd is not configured."""

    def increment(self, name: str, value: int = 1, tags: list[str] | None = None) -> None:
        pass

    def gauge(self, name: str, value: float, tags: list[str] | None = None) -> None:
        pass

    def histogram(self, name: str, value: float, tags: list[str] | None = None) -> None:
        pass

    def timing(self, name: str, ms: float, tags: list[str] | None = None) -> None:
        pass


class _DogStatsdMetrics:
    """Datadog DogStatsD with tag support."""

    def __init__(self, client: Any):
        self._client = client

    def increment(self, name: str, value: int = 1, tags: list[str] | None = None) -> None:
        try:
            self._client.increment(name, value=value, tags=tags or [])
        except Exception:
            pass

    def gauge(self, name: str, value: float, tags: list[str] | None = None) -> None:
        try:
            self._client.gauge(name, value, tags=tags or [])
        except Exception:
            pass

    def histogram(self, name: str, value: float, tags: list[str] | None = None) -> None:
        try:
            self._client.histogram(name, value, tags=tags or [])
        except Exception:
            pass

    def timing(self, name: str, ms: float, tags: list[str] | None = None) -> None:
        try:
            self._client.timing(name, ms, tags=tags or [])
        except Exception:
            pass


class _StatsdMetrics:
    """Basic statsd (no tags)."""

    def __init__(self, client: Any):
        self._client = client

    def increment(self, name: str, value: int = 1, tags: list[str] | None = None) -> None:
        try:
            self._client.incr(name, value)
        except Exception:
            pass

    def gauge(self, name: str, value: float, tags: list[str] | None = None) -> None:
        try:
            self._client.gauge(name, value)
        except Exception:
            pass

    def histogram(self, name: str, value: float, tags: list[str] | None = None) -> None:
        try:
            self._client.gauge(name, value)  # Fallback when histogram not available
        except Exception:
            pass

    def timing(self, name: str, ms: float, tags: list[str] | None = None) -> None:
        try:
            self._client.timing(name, ms)
        except Exception:
            pass


class TaskTimer:
    """Context manager to record task latency."""

    def __init__(self, metric_name: str, tags: list[str] | None = None):
        self._name = metric_name
        self._tags = tags or []
        self._start: float | None = None

    def __enter__(self) -> "TaskTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._start is not None:
            elapsed_ms = (time.perf_counter() - self._start) * 1000
            get_metrics().timing(self._name, elapsed_ms, tags=self._tags)
