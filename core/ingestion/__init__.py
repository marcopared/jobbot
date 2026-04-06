from core.ingestion.registry import (
    BackendRegistry,
    SourceAdapterRegistry,
    build_default_backend_registry,
    build_default_source_registry,
)
from core.ingestion.source_policies import SOURCE_POLICIES, get_source_policy
from core.ingestion.types import (
    AcquisitionArtifact,
    AcquisitionBatch,
    AcquisitionError,
    AcquisitionErrorType,
    AcquisitionProvenance,
    AcquisitionRecord,
    AcquisitionRequest,
    BackendPreference,
    FetchMode,
    SourceKind,
    SourcePolicy,
)

backend_registry = build_default_backend_registry()
source_registry = build_default_source_registry()

__all__ = [
    "AcquisitionArtifact",
    "AcquisitionBatch",
    "AcquisitionError",
    "AcquisitionErrorType",
    "AcquisitionProvenance",
    "AcquisitionRecord",
    "AcquisitionRequest",
    "BackendPreference",
    "BackendRegistry",
    "FetchMode",
    "SourceAdapterRegistry",
    "SourceKind",
    "SourcePolicy",
    "SOURCE_POLICIES",
    "backend_registry",
    "build_default_backend_registry",
    "build_default_source_registry",
    "get_source_policy",
    "source_registry",
]
