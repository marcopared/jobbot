from core.ingestion.sources.compatibility.canonical_connector_adapter import (
    CanonicalConnectorSourceAdapter,
    build_canonical_connector_adapter,
)
from core.ingestion.sources.compatibility.jobspy_scraper_adapter import (
    JobSpyScraperSourceAdapter,
    build_jobspy_scraper_adapter,
)

__all__ = [
    "CanonicalConnectorSourceAdapter",
    "JobSpyScraperSourceAdapter",
    "build_canonical_connector_adapter",
    "build_jobspy_scraper_adapter",
]
