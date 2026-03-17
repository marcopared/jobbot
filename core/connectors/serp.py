"""
SERP discovery connector (optional, feature-flagged, lower-confidence).

EXPLICIT STUB: This connector intentionally returns empty results. It enables
route/task wiring and feature-flag discipline without integrating a real SERP
API. Per IMPLEMENTATION_PLAN and ARCHITECTURE: SERP is optional and
feature-flagged; implement after AGG-1 and core automation are stable.
SERP-derived sources must remain lower-confidence.

When enabled, fetch_raw_jobs returns FetchResult(raw_jobs=[], stats={...}, error=None).
The discovery pipeline handles empty results cleanly (run completes with 0 inserted).
Never raises; safe to call regardless of params.
"""

from core.connectors.base import CanonicalJobPayload, FetchResult


class Serp1Connector:
    """
    Explicit stub SERP discovery connector.

    Returns empty results. Never raises. Enables route/task wiring and
    feature-flag discipline without external API calls.
    When implemented: use a SERP API (e.g. SerpAPI, Serper) with query-driven
    job search. Mark records as lower-confidence; never treat as canonical.
    """

    @property
    def source_name(self) -> str:
        return "serp1"

    def fetch_raw_jobs(self, **params: object) -> FetchResult:
        """
        Stub: always returns empty FetchResult. Never raises.
        Params (query, location, etc.) are accepted but ignored.
        """
        return FetchResult(
            raw_jobs=[],
            stats={"fetched": 0, "errors": 0},
            error=None,
        )

    def normalize(self, raw_job: dict, **context: object) -> CanonicalJobPayload | None:
        """Stub: not used when fetch returns empty. Returns None for any input."""
        return None


def create_serp1_connector() -> Serp1Connector:
    """Factory for Serp1Connector."""
    return Serp1Connector()
