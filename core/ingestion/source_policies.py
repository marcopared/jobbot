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
    "trueup": SourcePolicy(
        source_name="trueup",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="TRUEUP_ENABLED",
    ),
    "underdog": SourcePolicy(
        source_name="underdog",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="UNDERDOG_ENABLED",
    ),
    "startupjobs_nyc": SourcePolicy(
        source_name="startupjobs_nyc",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="STARTUPJOBS_NYC_ENABLED",
    ),
    "technyc": SourcePolicy(
        source_name="technyc",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="TECHNYC_ENABLED",
    ),
    "primary_vc": SourcePolicy(
        source_name="primary_vc",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="PRIMARY_VC_ENABLED",
    ),
    "greycroft": SourcePolicy(
        source_name="greycroft",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="GREYCROFT_ENABLED",
    ),
    "usv": SourcePolicy(
        source_name="usv",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="USV_ENABLED",
    ),
    "ventureloop": SourcePolicy(
        source_name="ventureloop",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="VENTURELOOP_ENABLED",
    ),
    "builtin_nyc": SourcePolicy(
        source_name="builtin_nyc",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="BUILTIN_NYC_ENABLED",
    ),
    "welcome_to_the_jungle": SourcePolicy(
        source_name="welcome_to_the_jungle",
        source_kind=SourceKind.PUBLIC_BOARD,
        source_role_default="discovery",
        requires_auth=False,
        backend_preference=BackendPreference.SCRAPLING.value,
        feature_flag_key="WELCOME_TO_THE_JUNGLE_ENABLED",
    ),
    "linkedin_jobs": SourcePolicy(
        source_name="linkedin_jobs",
        source_kind=SourceKind.BROWSER_AUTH,
        source_role_default="discovery",
        requires_auth=True,
        backend_preference=BackendPreference.BB_BROWSER.value,
        feature_flag_key="LINKEDIN_JOBS_ENABLED",
    ),
    "wellfound": SourcePolicy(
        source_name="wellfound",
        source_kind=SourceKind.BROWSER_AUTH,
        source_role_default="discovery",
        requires_auth=True,
        backend_preference=BackendPreference.BB_BROWSER.value,
        feature_flag_key="WELLFOUND_ENABLED",
    ),
    "yc": SourcePolicy(
        source_name="yc",
        source_kind=SourceKind.BROWSER_AUTH,
        source_role_default="discovery",
        requires_auth=True,
        backend_preference=BackendPreference.BB_BROWSER.value,
        feature_flag_key="YC_ENABLED",
    ),
}


def get_source_policy(source_name: str) -> SourcePolicy:
    try:
        return SOURCE_POLICIES[source_name]
    except KeyError as exc:
        raise KeyError(f"No source policy registered for '{source_name}'") from exc
