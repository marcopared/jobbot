from __future__ import annotations

from typing import Any

from core.connectors.base import FetchResult, RawJobWithProvenance, ProvenanceMetadata
from core.ingestion.backends.base import AcquisitionBackend, LegacyConnectorBackend
from core.ingestion.source_policies import get_source_policy
from core.ingestion.sources.base import SourceAdapter
from core.ingestion.types import AcquisitionBatch, AcquisitionRecord, SourcePolicy


class CanonicalConnectorSourceAdapter(SourceAdapter):
    def __init__(
        self,
        connector: Any,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        resolved_policy = policy or get_source_policy(connector.source_name)
        super().__init__(
            source_name=connector.source_name,
            policy=resolved_policy,
            backend=backend or LegacyConnectorBackend(),
        )
        self._connector = connector

    @property
    def connector(self) -> Any:
        return self._connector

    def acquire(self, **params: Any) -> AcquisitionBatch:
        return self.backend.acquire(
            self.source_name,
            fetch=self._connector.fetch_raw_jobs,
            params=params,
        )

    def normalize(self, acquired: AcquisitionRecord | dict[str, Any], **context: Any) -> Any | None:
        if isinstance(acquired, AcquisitionRecord):
            raw_payload = acquired.raw_payload
        else:
            raw_payload = acquired
        return self._connector.normalize(raw_payload, **context)

    def fetch_raw_jobs(self, **params: Any) -> FetchResult:
        batch = self.acquire(**params)
        return FetchResult(
            raw_jobs=[
                RawJobWithProvenance(
                    raw_payload=record.raw_payload,
                    provenance=ProvenanceMetadata(
                        fetch_timestamp=record.provenance.fetch_timestamp,
                        source_url=record.provenance.source_url,
                        connector_version=record.provenance.connector_version,
                    ),
                )
                for record in batch.records
            ],
            stats=dict(batch.stats),
            error=batch.error,
        )


def build_canonical_connector_adapter(
    connector: Any,
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> CanonicalConnectorSourceAdapter:
    return CanonicalConnectorSourceAdapter(connector=connector, policy=policy, backend=backend)
