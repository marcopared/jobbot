from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.db.models import ATSType, JobSource
from core.dedup import canonicalize_apply_url, compute_dedup_hash_from_raw


def normalize_url(url: str | None) -> str:
    """Canonical form of URL (strip params, fragment, trailing slash). Backward-compat alias."""
    return canonicalize_apply_url(url)


def compute_dedup_hash(
    title: str,
    company_name: str,
    url: str,
    location: str | None = None,
) -> str:
    """
    Compute dedup_hash from title, company, url, and optional location.
    Uses v1 spec: normalized company + title + location + canonical apply URL.
    """
    return compute_dedup_hash_from_raw(
        company=company_name,
        title=title,
        location=location,
        apply_url=url,
    )


@dataclass
class ScrapeParams:
    query: str
    location: str
    hours_old: int = 48
    results_wanted: int = 50


@dataclass
class NormalizedJob:
    title: str
    company_name: str
    location: str | None
    url: str
    apply_url: str | None
    description: str | None
    salary_min: int | None
    salary_max: int | None
    posted_at: datetime | None
    remote_flag: bool
    source: JobSource
    source_job_id: str | None
    raw_payload: dict | None = None


@dataclass
class ScrapeResult:
    jobs: list[NormalizedJob]
    stats: dict  # {"fetched": N, "errors": N}
    error: str | None = None


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, params: ScrapeParams) -> ScrapeResult:
        """Execute scrape and return normalized jobs."""
        ...


ATS_URL_PATTERNS = {
    "greenhouse": ["boards.greenhouse.io", "greenhouse.io/"],
    "lever": ["jobs.lever.co"],
    "ashby": ["jobs.ashbyhq.com", "ashbyhq.com/"],
    "workday": ["myworkdayjobs.com", "wd5.myworkday", "workday.com/"],
    "yc": ["workatastartup.com"],
}


def detect_ats_type(url: str) -> ATSType:
    url_lower = url.lower()
    for ats, patterns in ATS_URL_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return ATSType(ats)
    return ATSType.UNKNOWN
