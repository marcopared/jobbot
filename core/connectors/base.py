"""
Connector abstraction for v1 ingestion framework.

Each connector implements:
- fetch_raw_jobs(): retrieves raw job data from the source
- normalize(raw_job): maps source-specific payload to canonical schema

Raw payloads are stored in JSONB for debugging and replayability.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass
class ProvenanceMetadata:
    """Metadata describing the fetch provenance for a job."""

    fetch_timestamp: str
    source_url: str
    connector_version: str = "v1"


@dataclass
class CanonicalJobPayload:
    """
    Normalized job payload for insertion into the canonical Job schema.

    Fields required for dedup and display per SPEC §8.
    """

    source_name: str
    external_id: str
    title: str
    company: str
    location: str | None
    employment_type: str | None
    description: str | None
    apply_url: str | None
    source_url: str | None
    posted_at: datetime | None
    raw_payload: dict[str, Any]
    # For dedup plumbing: normalized strings used in hash computation
    normalized_title: str
    normalized_company: str
    normalized_location: str | None


@dataclass
class RawJobWithProvenance:
    """A raw job dict plus provenance metadata from the fetch."""

    raw_payload: dict[str, Any]
    provenance: ProvenanceMetadata


@dataclass
class FetchResult:
    """Result of a connector's fetch operation."""

    raw_jobs: list[RawJobWithProvenance]
    stats: dict[str, int]  # e.g. {"fetched": N, "errors": N}
    error: str | None = None


class ConnectorProtocol(Protocol):
    """Service contract for ingestion connectors."""

    @property
    def source_name(self) -> str:
        """Identifier for this connector (e.g. 'greenhouse')."""
        ...

    def fetch_raw_jobs(self, **params: Any) -> FetchResult:
        """
        Retrieve raw jobs from the source.
        Returns FetchResult with raw payloads and provenance metadata.
        """
        ...

    def normalize(self, raw_job: dict[str, Any], **context: Any) -> CanonicalJobPayload | None:
        """
        Map source-specific payload to canonical schema.
        Returns None if the job cannot be normalized (e.g. missing required fields).
        """
        ...
