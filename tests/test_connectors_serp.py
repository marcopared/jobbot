"""Tests for SERP1 discovery connector stub."""

import pytest

from core.connectors.serp import create_serp1_connector


def test_serp1_source_name():
    """SERP1 connector has source_name serp1."""
    connector = create_serp1_connector()
    assert connector.source_name == "serp1"


def test_serp1_fetch_returns_empty():
    """Stub returns empty FetchResult."""
    connector = create_serp1_connector()
    result = connector.fetch_raw_jobs(query="engineer")
    assert result.error is None
    assert result.stats["fetched"] == 0
    assert len(result.raw_jobs) == 0


def test_serp1_normalize_returns_none():
    """Stub normalize returns None (not used when fetch is empty)."""
    connector = create_serp1_connector()
    assert connector.normalize({}) is None


def test_serp1_fetch_never_raises():
    """Stub fetch never raises regardless of params."""
    connector = create_serp1_connector()
    connector.fetch_raw_jobs()
    connector.fetch_raw_jobs(query="x", location="y")
    connector.fetch_raw_jobs(unknown_param=123)


def test_serp1_fetch_result_structure():
    """Stub returns well-formed FetchResult with expected stats keys."""
    connector = create_serp1_connector()
    result = connector.fetch_raw_jobs(query="engineer")
    assert result.error is None
    assert result.raw_jobs == []
    assert result.stats["fetched"] == 0
    assert result.stats["errors"] == 0
