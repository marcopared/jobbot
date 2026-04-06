from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.types import AcquisitionBatch, AcquisitionRecord, SourcePolicy


class SourceAdapter(ABC):
    def __init__(self, *, source_name: str, policy: SourcePolicy, backend: AcquisitionBackend) -> None:
        self._source_name = source_name
        self._policy = policy
        self._backend = backend

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def policy(self) -> SourcePolicy:
        return self._policy

    @property
    def backend(self) -> AcquisitionBackend:
        return self._backend

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @abstractmethod
    def acquire(self, **params: Any) -> AcquisitionBatch:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, acquired: AcquisitionRecord | Any, **context: Any) -> Any | None:
        raise NotImplementedError
