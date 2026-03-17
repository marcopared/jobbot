"""Tests for URL provider detection (Greenhouse, Lever, Ashby)."""

import pytest

from core.connectors.url_provider import (
    SUPPORTED_PROVIDERS,
    detect_provider,
    is_supported_url,
    parse_supported_url,
)


def test_detect_provider_greenhouse():
    """Greenhouse job URLs are detected."""
    url = "https://boards.greenhouse.io/acme/jobs/127817"
    assert detect_provider(url) == "greenhouse"
    url2 = "http://jobs.greenhouse.io/acme/jobs/999"
    assert detect_provider(url2) == "greenhouse"


def test_detect_provider_lever():
    """Lever job URLs are detected."""
    url = "https://jobs.lever.co/netflix/abc-123"
    assert detect_provider(url) == "lever"
    url2 = "https://jobs.lever.co/leverdemo/33538a2f-d27d-4a96-8f05-fa4b0e4d940e/apply"
    assert detect_provider(url2) == "lever"


def test_detect_provider_ashby():
    """Ashby job URLs are detected."""
    url = "https://jobs.ashbyhq.com/ashby/xyz-role"
    assert detect_provider(url) == "ashby"
    url2 = "https://jobs.ashbyhq.com/ExampleCompany/abc-123"
    assert detect_provider(url2) == "ashby"


def test_detect_provider_unsupported():
    """Unsupported URLs return None."""
    assert detect_provider("https://example.com/jobs/1") is None
    assert detect_provider("https://linkedin.com/jobs/123") is None
    assert detect_provider("") is None
    assert detect_provider("  ") is None


def test_parse_supported_url_greenhouse():
    """Parse Greenhouse URL extracts board_token and job_id."""
    url = "https://boards.greenhouse.io/acme/jobs/127817"
    r = parse_supported_url(url)
    assert r is not None
    assert r.provider == "greenhouse"
    assert r.board_token == "acme"
    assert r.job_id == "127817"


def test_parse_supported_url_lever():
    """Parse Lever URL extracts client_name and job_id."""
    url = "https://jobs.lever.co/netflix/abc-123"
    r = parse_supported_url(url)
    assert r is not None
    assert r.provider == "lever"
    assert r.client_name == "netflix"
    assert r.job_id == "abc-123"
    url_apply = "https://jobs.lever.co/netflix/uuid-here/apply"
    r2 = parse_supported_url(url_apply)
    assert r2 is not None
    assert r2.provider == "lever"
    assert r2.client_name == "netflix"
    assert r2.job_id == "uuid-here"


def test_parse_supported_url_ashby():
    """Parse Ashby URL extracts job_board_name and job_slug."""
    url = "https://jobs.ashbyhq.com/ashby/xyz-role"
    r = parse_supported_url(url)
    assert r is not None
    assert r.provider == "ashby"
    assert r.job_board_name == "ashby"
    assert r.job_slug == "xyz-role"
    assert r.job_id == "xyz-role"


def test_parse_supported_url_returns_none_for_unsupported():
    """Parse returns None for unsupported URLs."""
    assert parse_supported_url("https://example.com/job") is None
    assert parse_supported_url("") is None


def test_is_supported_url():
    """is_supported_url returns True for supported, False otherwise."""
    assert is_supported_url("https://boards.greenhouse.io/acme/jobs/1") is True
    assert is_supported_url("https://jobs.lever.co/x/y") is True
    assert is_supported_url("https://jobs.ashbyhq.com/board/slug") is True
    assert is_supported_url("https://other.com/jobs") is False
    assert is_supported_url("") is False


def test_supported_providers_constant():
    """SUPPORTED_PROVIDERS includes greenhouse, lever, ashby."""
    assert SUPPORTED_PROVIDERS == frozenset({"greenhouse", "lever", "ashby"})
