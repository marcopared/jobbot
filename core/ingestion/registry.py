from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from core.ingestion.backends.base import (
    AcquisitionBackend,
    LegacyConnectorBackend,
    LegacyScraperBackend,
)
from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.compatibility.canonical_connector_adapter import (
    build_canonical_connector_adapter,
)
from core.ingestion.sources.compatibility.jobspy_scraper_adapter import (
    build_jobspy_scraper_adapter,
)
from core.ingestion.sources.public_boards import (
    build_builtin_nyc_adapter,
    build_startupjobs_nyc_adapter,
    build_trueup_adapter,
    build_underdog_adapter,
    build_ventureloop_adapter,
    build_welcome_to_the_jungle_adapter,
)


TBackend = TypeVar("TBackend", bound=AcquisitionBackend)


class BackendRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], AcquisitionBackend]] = {}

    def register(self, name: str, factory: Callable[[], TBackend] | type[TBackend]) -> None:
        if name in self._factories:
            raise ValueError(f"Backend '{name}' is already registered")
        if isinstance(factory, type):
            self._factories[name] = factory
            return
        self._factories[name] = factory

    def create(self, name: str) -> AcquisitionBackend:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise KeyError(f"Backend '{name}' is not registered") from exc
        return factory()

    def has(self, name: str) -> bool:
        return name in self._factories


class SourceAdapterRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Any]] = {}

    def register(self, source_name: str, factory: Callable[..., Any]) -> None:
        if source_name in self._factories:
            raise ValueError(f"Source adapter '{source_name}' is already registered")
        self._factories[source_name] = factory

    def create(self, source_name: str, **kwargs: Any) -> Any:
        try:
            factory = self._factories[source_name]
        except KeyError as exc:
            raise KeyError(f"Source adapter '{source_name}' is not registered") from exc
        return factory(**kwargs)

    def has(self, source_name: str) -> bool:
        return source_name in self._factories


def build_default_backend_registry() -> BackendRegistry:
    registry = BackendRegistry()
    registry.register("legacy_connector", LegacyConnectorBackend)
    registry.register("legacy_scraper", LegacyScraperBackend)
    registry.register("scrapling", ScraplingFetchBackend)
    return registry


def build_default_source_registry() -> SourceAdapterRegistry:
    registry = SourceAdapterRegistry()
    registry.register("greenhouse", build_canonical_connector_adapter)
    registry.register("lever", build_canonical_connector_adapter)
    registry.register("ashby", build_canonical_connector_adapter)
    registry.register("jobspy", build_jobspy_scraper_adapter)
    registry.register("trueup", build_trueup_adapter)
    registry.register("underdog", build_underdog_adapter)
    registry.register("startupjobs_nyc", build_startupjobs_nyc_adapter)
    registry.register("ventureloop", build_ventureloop_adapter)
    registry.register("builtin_nyc", build_builtin_nyc_adapter)
    registry.register("welcome_to_the_jungle", build_welcome_to_the_jungle_adapter)
    return registry
