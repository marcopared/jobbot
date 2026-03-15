"""Task failure visibility for dead-letter / debugging (EPIC 10).

Stores recent task failures in Redis for diagnosability. Celery signals
record failures; API exposes GET /api/debug/failures.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REDIS_KEY = "jobbot:task_failures"
MAX_FAILURES = 100


@dataclass
class TaskFailureRecord:
    """Record of a task that failed after max retries."""

    task_name: str
    args: list
    kwargs: dict
    error: str
    timestamp: str
    retries: int
    job_id: str | None = None
    run_id: str | None = None


def record_task_failure(
    task_name: str,
    args: tuple,
    kwargs: dict,
    error: str,
    retries: int = 0,
    redis_url: str | None = None,
) -> None:
    """Append a failure record to Redis list for visibility."""
    if not redis_url:
        return
    try:
        import redis
        ts = datetime.now(timezone.utc).isoformat()
        # Extract common identifiers from args/kwargs
        job_id = None
        run_id = None
        if args and len(args) >= 1:
            a0 = args[0]
            if isinstance(a0, str) and len(a0) == 36:  # UUID-like
                if "run" in task_name.lower() or task_name in ("ingest_greenhouse", "scrape_jobspy"):
                    run_id = a0
                else:
                    job_id = a0
        if kwargs.get("run_id"):
            run_id = str(kwargs["run_id"])
        if kwargs.get("job_id"):
            job_id = str(kwargs["job_id"])

        record = TaskFailureRecord(
            task_name=task_name,
            args=[str(a) for a in args[:5]],  # Truncate for storage
            kwargs={k: str(v)[:200] for k, v in list(kwargs.items())[:10]},
            error=str(error)[:1000],
            timestamp=ts,
            retries=retries,
            job_id=job_id,
            run_id=run_id,
        )
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        payload = json.dumps(asdict(record))
        client.lpush(REDIS_KEY, payload)
        client.ltrim(REDIS_KEY, 0, MAX_FAILURES - 1)
        client.expire(REDIS_KEY, 86400 * 7)  # 7 days TTL
        client.close()
    except Exception as e:
        logger.debug("Failed to record task failure to Redis: %s", e)


def get_recent_failures(redis_url: str | None, limit: int = 50) -> list[dict]:
    """Fetch recent failure records from Redis."""
    if not redis_url:
        return []
    try:
        import redis
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        raw = client.lrange(REDIS_KEY, 0, limit - 1)
        client.close()
        out = []
        for s in raw or []:
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError:
                pass
        return out
    except Exception as e:
        logger.debug("Failed to fetch task failures from Redis: %s", e)
        return []
