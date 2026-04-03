from core.ingestion.backends.base import (
    AcquisitionBackend,
    LegacyConnectorBackend,
    LegacyScraperBackend,
)
from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend

__all__ = [
    "AcquisitionBackend",
    "LegacyConnectorBackend",
    "LegacyScraperBackend",
    "ScraplingFetchBackend",
]
