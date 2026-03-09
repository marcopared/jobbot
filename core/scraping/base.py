import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from core.db.models import ATSType, JobSource


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


def normalize_url(url: str) -> str:
    """Strip tracking params, fragments, trailing slashes."""
    parsed = urlparse(url)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return clean


def compute_dedup_hash(title: str, company_name: str, url: str) -> str:
    normalized = (
        title.strip().lower()
        + "|"
        + company_name.strip().lower()
        + "|"
        + normalize_url(url).lower()
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


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
