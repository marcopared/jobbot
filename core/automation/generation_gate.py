"""Generation gate: decide when to auto-generate resumes (ARCH §10).

Rules:
- Canonical ATS / URL ingest: eligible at moderate score threshold.
- AGG-1 discovery: eligible only at stricter score + content/confidence threshold.
- SERP-only unresolved: not eligible by default.

JobSpy (source=jobspy, source_role=discovery): Uses generic discovery branch below.
Same as AGG-1: score >= discovery_agg1_score_threshold (70 default) plus content
quality (confidence >= 0.7, description >= 200 chars or content_quality_score >= 0.6).
Intentional: discovery sources get stricter rules; no auto-gen for low-confidence jobs.
"""

from dataclasses import dataclass

from core.db.models import Job, SourceRole


@dataclass
class GateConfig:
    """Configurable thresholds for generation gate."""

    # Feature flag
    auto_generation_enabled: bool = False

    # Canonical ATS / URL ingest
    canonical_score_threshold: float = 60.0

    # AGG-1 discovery: stricter
    discovery_agg1_score_threshold: float = 70.0
    discovery_agg1_confidence_min: float = 0.7
    discovery_agg1_content_quality_min: float = 0.6
    discovery_agg1_description_min_len: int = 200

    # SERP: not eligible by default
    discovery_serp_eligible: bool = False


def _is_canonical(job: Job) -> bool:
    """True if job is from canonical ATS or URL ingest."""
    role = job.source_role
    source = (job.source or "").lower()
    if role in (SourceRole.CANONICAL.value, SourceRole.URL_INGEST.value):
        return True
    if role is None and source in ("greenhouse", "lever", "ashby"):
        return True
    return False


def _is_discovery_agg1(job: Job) -> bool:
    """True if job is from AGG-1 discovery."""
    source = (job.source or "").lower()
    if job.source_role == SourceRole.DISCOVERY.value and source == "agg1":
        return True
    return False


def _is_discovery_serp(job: Job) -> bool:
    """True if job is from SERP discovery."""
    source = (job.source or "").lower()
    if job.source_role == SourceRole.DISCOVERY.value and source in ("serp1", "serp"):
        return True
    return False


def _has_content_quality(job: Job, min_confidence: float, min_content: float, min_desc_len: int) -> bool:
    """True if job has sufficient content quality for discovery auto-gen."""
    conf = job.source_confidence or 0.0
    cq = job.content_quality_score
    desc_len = len(job.description or "")
    if conf >= min_confidence and (cq is None or cq >= min_content):
        return True
    if conf >= min_confidence and desc_len >= min_desc_len:
        return True
    return False


def evaluate_generation_eligibility(job: Job, config: GateConfig) -> tuple[bool, str]:
    """
    Evaluate if job qualifies for auto-generation.

    Returns (eligible: bool, reason: str).
    """
    if not config.auto_generation_enabled:
        return False, "auto_generation_disabled"

    if job.stale_flag:
        return False, "stale"

    if not job.apply_url:
        return False, "no_apply_url"

    if not job.description:
        return False, "no_description"

    if job.artifact_ready_at is not None:
        return False, "already_artifact_ready"

    score = job.score_total or 0.0

    # Canonical ATS / URL ingest: moderate threshold
    if _is_canonical(job):
        if score >= config.canonical_score_threshold:
            return True, "canonical_eligible"
        return False, f"canonical_score_below_{config.canonical_score_threshold}"

    # SERP discovery: not eligible by default
    if _is_discovery_serp(job):
        if not config.discovery_serp_eligible:
            return False, "serp_not_eligible_by_default"
        if score < config.discovery_agg1_score_threshold:
            return False, f"serp_score_below_{config.discovery_agg1_score_threshold}"
        return True, "serp_eligible_override"

    # AGG-1 discovery: stricter threshold + content/confidence
    if _is_discovery_agg1(job):
        if score < config.discovery_agg1_score_threshold:
            return False, f"agg1_score_below_{config.discovery_agg1_score_threshold}"
        if not _has_content_quality(
            job,
            config.discovery_agg1_confidence_min,
            config.discovery_agg1_content_quality_min,
            config.discovery_agg1_description_min_len,
        ):
            return False, "agg1_insufficient_content_confidence"
        return True, "agg1_eligible"

    # JobSpy and other discovery sources: use AGG-1 rules when source_role=discovery
    if job.source_role == SourceRole.DISCOVERY.value:
        if score < config.discovery_agg1_score_threshold:
            return False, f"discovery_score_below_{config.discovery_agg1_score_threshold}"
        if not _has_content_quality(
            job,
            config.discovery_agg1_confidence_min,
            config.discovery_agg1_content_quality_min,
            config.discovery_agg1_description_min_len,
        ):
            return False, "discovery_insufficient_content_confidence"
        return True, "discovery_eligible"

    # Unknown source: ineligible
    return False, "unknown_source"


def gate_config_from_settings(settings) -> GateConfig:
    """Build GateConfig from API Settings."""
    return GateConfig(
        auto_generation_enabled=settings.enable_auto_resume_generation,
        canonical_score_threshold=settings.generation_canonical_score_threshold,
        discovery_agg1_score_threshold=settings.generation_discovery_score_threshold,
        discovery_agg1_confidence_min=settings.generation_discovery_confidence_min,
    )
