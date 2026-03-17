"""Generation gate unit tests (PR5, ARCH §10).

Tests evaluate_generation_eligibility for canonical, AGG-1 discovery,
SERP discovery, and edge cases.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from core.automation.generation_gate import (
    GateConfig,
    evaluate_generation_eligibility,
)


def _mock_job(
    source: str = "greenhouse",
    source_role: str | None = "canonical",
    score_total: float = 65.0,
    apply_url: str = "https://example.com/apply",
    description: str = "Build APIs. Python.",
    artifact_ready_at=None,
    stale_flag: bool = False,
    source_confidence: float | None = None,
    content_quality_score: float | None = None,
):
    """Create a mock Job-like object for gate tests."""
    j = MagicMock()
    j.source = source
    j.source_role = source_role
    j.score_total = score_total
    j.apply_url = apply_url
    j.description = description
    j.artifact_ready_at = artifact_ready_at
    j.stale_flag = stale_flag
    j.source_confidence = source_confidence
    j.content_quality_score = content_quality_score
    return j


def test_gate_disabled_returns_ineligible():
    """When auto_generation_enabled=False, all jobs are ineligible."""
    config = GateConfig(auto_generation_enabled=False)
    job = _mock_job(score_total=80.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert reason == "auto_generation_disabled"


def test_canonical_eligible_at_threshold():
    """Canonical job with score >= canonical_score_threshold is eligible."""
    config = GateConfig(
        auto_generation_enabled=True,
        canonical_score_threshold=60.0,
    )
    job = _mock_job(source="greenhouse", source_role="canonical", score_total=65.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert eligible
    assert reason == "canonical_eligible"


def test_canonical_ineligible_below_threshold():
    """Canonical job with score < threshold is ineligible."""
    config = GateConfig(
        auto_generation_enabled=True,
        canonical_score_threshold=60.0,
    )
    job = _mock_job(source="greenhouse", source_role="canonical", score_total=55.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert "canonical_score_below" in reason


def test_url_ingest_eligible():
    """URL ingest job (source_role=url_ingest) uses canonical threshold."""
    config = GateConfig(
        auto_generation_enabled=True,
        canonical_score_threshold=60.0,
    )
    job = _mock_job(source="greenhouse", source_role="url_ingest", score_total=65.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert eligible
    assert reason == "canonical_eligible"


def test_legacy_canonical_no_source_role():
    """Job with source in (greenhouse, lever, ashby) and no source_role treated as canonical."""
    config = GateConfig(auto_generation_enabled=True, canonical_score_threshold=60.0)
    for src in ("greenhouse", "lever", "ashby"):
        job = _mock_job(source=src, source_role=None, score_total=62.0)
        eligible, reason = evaluate_generation_eligibility(job, config)
        assert eligible, f"Expected eligible for source={src}"
        assert reason == "canonical_eligible"


def test_serp_not_eligible_by_default():
    """SERP discovery job is not eligible by default."""
    config = GateConfig(
        auto_generation_enabled=True,
        discovery_serp_eligible=False,
    )
    job = _mock_job(
        source="serp1",
        source_role="discovery",
        score_total=80.0,
        source_confidence=0.8,
    )
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert reason == "serp_not_eligible_by_default"


def test_agg1_eligible_with_confidence_and_content():
    """AGG-1 discovery job with score + confidence + content quality is eligible."""
    config = GateConfig(
        auto_generation_enabled=True,
        discovery_agg1_score_threshold=70.0,
        discovery_agg1_confidence_min=0.7,
        discovery_agg1_content_quality_min=0.6,
        discovery_agg1_description_min_len=200,
    )
    job = _mock_job(
        source="agg1",
        source_role="discovery",
        score_total=75.0,
        description="A" * 250,
        source_confidence=0.8,
    )
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert eligible
    assert reason == "agg1_eligible"


def test_jobspy_discovery_eligible_with_source_role_and_quality():
    """JobSpy with source_role=discovery uses discovery rules; eligible when score + content met."""
    config = GateConfig(
        auto_generation_enabled=True,
        discovery_agg1_score_threshold=70.0,
        discovery_agg1_confidence_min=0.7,
        discovery_agg1_description_min_len=200,
    )
    job = _mock_job(
        source="jobspy",
        source_role="discovery",
        score_total=75.0,
        description="A" * 250,
        source_confidence=0.8,
    )
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert eligible
    assert reason == "discovery_eligible"


def test_jobspy_discovery_ineligible_below_threshold():
    """JobSpy discovery job below score threshold is ineligible."""
    config = GateConfig(
        auto_generation_enabled=True,
        discovery_agg1_score_threshold=70.0,
    )
    job = _mock_job(
        source="jobspy",
        source_role="discovery",
        score_total=65.0,
        source_confidence=0.9,
        description="A" * 300,
    )
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert "discovery_score_below" in reason


def test_agg1_ineligible_below_score():
    """AGG-1 job below discovery threshold is ineligible."""
    config = GateConfig(
        auto_generation_enabled=True,
        discovery_agg1_score_threshold=70.0,
    )
    job = _mock_job(
        source="agg1",
        source_role="discovery",
        score_total=65.0,
        source_confidence=0.9,
        description="A" * 300,
    )
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert "agg1_score_below" in reason


def test_no_apply_url_ineligible():
    """Job without apply_url is ineligible."""
    config = GateConfig(auto_generation_enabled=True)
    job = _mock_job(apply_url=None, score_total=80.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert reason == "no_apply_url"


def test_no_description_ineligible():
    """Job without description is ineligible."""
    config = GateConfig(auto_generation_enabled=True)
    job = _mock_job(description=None, score_total=80.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert reason == "no_description"


def test_stale_ineligible():
    """Job with stale_flag is ineligible."""
    config = GateConfig(auto_generation_enabled=True)
    job = _mock_job(stale_flag=True, score_total=80.0)
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert reason == "stale"


def test_already_artifact_ready_ineligible():
    """Job with artifact_ready_at set is ineligible (skip re-gen)."""
    config = GateConfig(auto_generation_enabled=True)
    job = _mock_job(
        artifact_ready_at=datetime.now(timezone.utc),
        score_total=80.0,
    )
    eligible, reason = evaluate_generation_eligibility(job, config)
    assert not eligible
    assert reason == "already_artifact_ready"
