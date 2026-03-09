from core.scraping.base import (
    BaseScraper,
    ScrapeParams,
    ScrapeResult,
    NormalizedJob,
    compute_dedup_hash,
    normalize_url,
    detect_ats_type,
    ATS_URL_PATTERNS,
)
from core.scraping.jobspy_scraper import JobSpyScraper

__all__ = [
    "BaseScraper",
    "ScrapeParams",
    "ScrapeResult",
    "NormalizedJob",
    "compute_dedup_hash",
    "normalize_url",
    "detect_ats_type",
    "ATS_URL_PATTERNS",
    "JobSpyScraper",
]
