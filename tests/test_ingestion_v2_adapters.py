from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.connectors.base import (
    CanonicalJobPayload,
    FetchResult,
    ProvenanceMetadata,
    RawJobWithProvenance,
)
from core.db.models import JobSource
from core.ingestion.registry import (
    build_default_backend_registry,
    build_default_source_registry,
)
from core.ingestion.sources.auth_boards import (
    LinkedInJobsSourceAdapter,
    WellfoundSourceAdapter,
    YCJobsSourceAdapter,
)
from core.ingestion.sources.compatibility import (
    CanonicalConnectorSourceAdapter,
    JobSpyScraperSourceAdapter,
)
from core.ingestion.sources.portfolio_boards import (
    GreycroftSourceAdapter,
    PrimaryVCSourceAdapter,
    TechNYCSourceAdapter,
    USVSourceAdapter,
)
from core.ingestion.sources.public_boards import (
    BuiltInNYCSourceAdapter,
    StartupJobsNYCSourceAdapter,
    UnsupportedPublicBoardSourceAdapter,
    WelcomeToTheJungleSourceAdapter,
)
from core.scraping.base import NormalizedJob, ScrapeParams, ScrapeResult


class _FakeCanonicalConnector:
    source_name = "greenhouse"

    def fetch_raw_jobs(self, **params: Any) -> FetchResult:
        return FetchResult(
            raw_jobs=[
                RawJobWithProvenance(
                    raw_payload={
                        "id": "gh-1",
                        "title": "Platform Engineer",
                        "company": "Example Co",
                        "location": "Remote",
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/1",
                    },
                    provenance=ProvenanceMetadata(
                        fetch_timestamp="2026-04-02T12:00:00+00:00",
                        source_url="https://boards.greenhouse.io/example",
                        connector_version="test-connector",
                    ),
                )
            ],
            stats={"fetched": 1, "errors": 0},
            error=None,
        )

    def normalize(self, raw_job: dict[str, Any], **context: Any) -> CanonicalJobPayload | None:
        return CanonicalJobPayload(
            source_name="greenhouse",
            external_id=str(raw_job["id"]),
            title=str(raw_job["title"]),
            company=str(raw_job["company"]),
            location=str(raw_job["location"]),
            employment_type=None,
            description=None,
            apply_url=str(raw_job["absolute_url"]),
            source_url=str(raw_job["absolute_url"]),
            posted_at=datetime(2026, 4, 2, tzinfo=UTC),
            raw_payload=raw_job,
            normalized_title="platform engineer",
            normalized_company="example co",
            normalized_location="remote",
        )


class _FakeJobSpyScraper:
    def scrape(self, params: ScrapeParams) -> ScrapeResult:
        assert params.query == "backend engineer"
        return ScrapeResult(
            jobs=[
                NormalizedJob(
                    title="Backend Engineer",
                    company_name="JobSpy Co",
                    location="Remote",
                    url="https://jobspy.example/jobs/1",
                    apply_url="https://jobspy.example/apply/1",
                    description="Discovery posting",
                    salary_min=100000,
                    salary_max=150000,
                    posted_at=datetime(2026, 4, 1, tzinfo=UTC),
                    remote_flag=True,
                    source=JobSource.JOBSPY,
                    source_job_id="jobspy-1",
                    raw_payload={
                        "id": "jobspy-1",
                        "title": "Backend Engineer",
                        "company": "JobSpy Co",
                        "location": "Remote",
                        "job_url": "https://jobspy.example/jobs/1",
                        "job_url_direct": "https://jobspy.example/apply/1",
                        "description": "Discovery posting",
                        "is_remote": True,
                    },
                )
            ],
            stats={"fetched": 1, "errors": 0},
            error=None,
        )


def test_source_registry_lookup_returns_compatibility_adapters():
    registry = build_default_source_registry()

    canonical_adapter = registry.create("greenhouse", connector=_FakeCanonicalConnector())
    jobspy_adapter = registry.create("jobspy", scraper=_FakeJobSpyScraper())
    startupjobs_adapter = registry.create("startupjobs_nyc")
    technyc_adapter = registry.create("technyc")
    primary_vc_adapter = registry.create("primary_vc")
    greycroft_adapter = registry.create("greycroft")
    usv_adapter = registry.create("usv")
    builtin_adapter = registry.create("builtin_nyc")
    wttj_adapter = registry.create("welcome_to_the_jungle")
    trueup_adapter = registry.create("trueup")
    linkedin_adapter = registry.create("linkedin_jobs")
    wellfound_adapter = registry.create("wellfound")
    yc_adapter = registry.create("yc")

    assert isinstance(canonical_adapter, CanonicalConnectorSourceAdapter)
    assert canonical_adapter.source_name == "greenhouse"
    assert canonical_adapter.policy.backend_preference == "legacy_connector"

    assert isinstance(jobspy_adapter, JobSpyScraperSourceAdapter)
    assert jobspy_adapter.source_name == "jobspy"
    assert jobspy_adapter.policy.backend_preference == "legacy_scraper"

    assert isinstance(startupjobs_adapter, StartupJobsNYCSourceAdapter)
    assert startupjobs_adapter.policy.backend_preference == "scrapling"
    assert startupjobs_adapter.policy.source_role_default == "discovery"

    assert isinstance(technyc_adapter, TechNYCSourceAdapter)
    assert technyc_adapter.policy.backend_preference == "scrapling"

    assert isinstance(primary_vc_adapter, PrimaryVCSourceAdapter)
    assert primary_vc_adapter.policy.backend_preference == "scrapling"

    assert isinstance(greycroft_adapter, GreycroftSourceAdapter)
    assert greycroft_adapter.policy.backend_preference == "scrapling"

    assert isinstance(usv_adapter, USVSourceAdapter)
    assert usv_adapter.policy.backend_preference == "scrapling"

    assert isinstance(builtin_adapter, BuiltInNYCSourceAdapter)
    assert builtin_adapter.policy.backend_preference == "scrapling"

    assert isinstance(wttj_adapter, WelcomeToTheJungleSourceAdapter)
    assert wttj_adapter.policy.backend_preference == "scrapling"

    assert isinstance(trueup_adapter, UnsupportedPublicBoardSourceAdapter)
    assert trueup_adapter.policy.backend_preference == "scrapling"

    assert isinstance(linkedin_adapter, LinkedInJobsSourceAdapter)
    assert linkedin_adapter.policy.backend_preference == "bb_browser"
    assert linkedin_adapter.policy.requires_auth is True

    assert isinstance(wellfound_adapter, WellfoundSourceAdapter)
    assert wellfound_adapter.policy.backend_preference == "bb_browser"

    assert isinstance(yc_adapter, YCJobsSourceAdapter)
    assert yc_adapter.policy.backend_preference == "bb_browser"


def test_backend_registry_lookup_returns_compatibility_backends():
    registry = build_default_backend_registry()

    connector_backend = registry.create("legacy_connector")
    scraper_backend = registry.create("legacy_scraper")
    bb_browser_backend = registry.create("bb_browser")

    assert connector_backend.name == "legacy_connector"
    assert scraper_backend.name == "legacy_scraper"
    assert bb_browser_backend.name == "bb_browser"


def test_canonical_connector_compatibility_adapter_preserves_contract():
    adapter = CanonicalConnectorSourceAdapter(_FakeCanonicalConnector())

    result = adapter.fetch_raw_jobs(include_content=True)
    assert result.error is None
    assert result.stats == {"fetched": 1, "errors": 0}
    assert result.raw_jobs[0].raw_payload["id"] == "gh-1"
    assert result.raw_jobs[0].provenance.connector_version == "test-connector"

    normalized = adapter.normalize(result.raw_jobs[0].raw_payload)
    assert normalized is not None
    assert normalized.external_id == "gh-1"
    assert normalized.company == "Example Co"
    assert normalized.apply_url == "https://boards.greenhouse.io/example/jobs/1"


def test_jobspy_compatibility_adapter_preserves_scrape_contract():
    adapter = JobSpyScraperSourceAdapter(_FakeJobSpyScraper())
    params = ScrapeParams(query="backend engineer", location="Remote", hours_old=24, results_wanted=10)

    result = adapter.scrape(params)
    assert result.error is None
    assert result.stats == {"fetched": 1, "errors": 0}
    assert len(result.jobs) == 1

    job = result.jobs[0]
    assert job.title == "Backend Engineer"
    assert job.company_name == "JobSpy Co"
    assert job.apply_url == "https://jobspy.example/apply/1"

    batch = adapter.acquire(params=params)
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.title == "Backend Engineer"
    assert normalized.source_job_id == "jobspy-1"
