from __future__ import annotations

from core.ingestion.types import BackendPreference, SourceKind, SourcePolicy


SOURCE_POLICIES: dict[str, SourcePolicy] = {
    "greenhouse": SourcePolicy(
        source_name="greenhouse",
        source_kind=SourceKind.CANONICAL_API,
        source_role_default="canonical",
        requires_auth=False,
        backend_preference=BackendPreference.LEGACY_CONNECTOR.value,
        feature_flag_key="GREENHOUSE_ENABLED",
    ),
    "lever": SourcePolicy(
        source_name="lever",
        source_kind=SourceKind.CANONICAL_API,
        source_role_default="canonical",
        requires_auth=False,
        backend_preference=BackendPreference.LEGACY_CONNECTOR.value,
        feature_flag_key="LEVER_ENABLED",
    ),
    "ashby": SourcePolicy(
        source_name="ashby",
        source_kind=SourceKind.CANONICAL_API,
        source_role_default="canonical",
        requires_auth=False,
        backend_preference=BackendPreference.LEGACY_CONNECTOR.value,
        feature_flag_key="ASHBY_ENABLED",
    ),
    "jobspy": SourcePolicy(
        source_name="jobspy",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.LEGACY_SCRAPER.value,
        feature_flag_key="JOBSPY_ENABLED",
    ),
}


def get_source_policy(source_name: str) -> SourcePolicy:
    try:
        return SOURCE_POLICIES[source_name]
    except KeyError as exc:
        raise KeyError(f"No source policy registered for '{source_name}'") from exc
