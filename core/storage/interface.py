"""Storage abstraction for resume artifacts (EPIC 7).

S3 in production, local filesystem fallback in development.
"""

import logging
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class StoreResult:
    """Result of storing an artifact."""

    def __init__(
        self,
        storage_key: str,
        file_url: str | None = None,
        local_path: str | None = None,
    ):
        self.storage_key = storage_key
        self.file_url = file_url
        self.local_path = local_path


class ArtifactStorage(Protocol):
    """Interface for artifact storage."""

    def store(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> StoreResult:
        """Store artifact bytes. Returns storage key and URL/path for retrieval."""
        ...

    def get_local_path(self, key: str) -> Path | None:
        """Return local filesystem path if using local storage; None for S3."""
        ...
