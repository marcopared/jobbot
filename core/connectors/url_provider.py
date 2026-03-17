"""
Deterministic URL provider detection for supported ATS job URLs.

Detects Greenhouse, Lever, Ashby job URLs and extracts identifiers
for connector-based ingestion. Returns clean unsupported-provider errors.
"""

import re
from dataclasses import dataclass
from typing import Literal

SUPPORTED_PROVIDERS = frozenset({"greenhouse", "lever", "ashby"})

# Greenhouse: boards.greenhouse.io/{board}/jobs/{id} or jobs.greenhouse.io
_GREENHOUSE_PATTERN = re.compile(
    r"https?://(?:boards\.greenhouse\.io|jobs\.greenhouse\.io)/([a-zA-Z0-9_-]+)/jobs/(\d+)",
    re.IGNORECASE,
)

# Lever: jobs.lever.co/{company}/{id} or jobs.lever.co/{company}/{id}/apply
_LEVER_PATTERN = re.compile(
    r"https?://jobs\.lever\.co/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)(?:/apply)?/?$",
    re.IGNORECASE,
)

# Ashby: jobs.ashbyhq.com/{board}/{slug} - slug can be UUID or custom
_ASHBY_PATTERN = re.compile(
    r"https?://jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/?$",
    re.IGNORECASE,
)


@dataclass
class UrlParseResult:
    """Parsed URL result for supported ATS providers."""

    provider: Literal["greenhouse", "lever", "ashby"]
    board_token: str | None = None  # greenhouse board_token
    job_id: str | None = None  # external id for the job
    client_name: str | None = None  # lever company slug
    job_board_name: str | None = None  # ashby job board name
    job_slug: str | None = None  # ashby job slug


def detect_provider(url: str) -> Literal["greenhouse", "lever", "ashby"] | None:
    """
    Detect which supported ATS provider a URL belongs to.

    Returns provider name or None if not a supported job URL.
    """
    url = (url or "").strip()
    if not url:
        return None
    if _GREENHOUSE_PATTERN.match(url):
        return "greenhouse"
    if _LEVER_PATTERN.match(url):
        return "lever"
    if _ASHBY_PATTERN.match(url):
        return "ashby"
    return None


def parse_supported_url(url: str) -> UrlParseResult | None:
    """
    Parse a supported ATS job URL and extract identifiers.

    Returns UrlParseResult for supported URLs, None otherwise.
    """
    url = (url or "").strip()
    if not url:
        return None

    m = _GREENHOUSE_PATTERN.match(url)
    if m:
        return UrlParseResult(
            provider="greenhouse",
            board_token=m.group(1),
            job_id=m.group(2),
        )

    m = _LEVER_PATTERN.match(url)
    if m:
        return UrlParseResult(
            provider="lever",
            client_name=m.group(1),
            job_id=m.group(2),
        )

    m = _ASHBY_PATTERN.match(url)
    if m:
        return UrlParseResult(
            provider="ashby",
            job_board_name=m.group(1),
            job_slug=m.group(2),
            job_id=m.group(2),
        )

    return None


def is_supported_url(url: str) -> bool:
    """Return True if the URL is a supported ATS job URL."""
    return parse_supported_url(url) is not None
