from __future__ import annotations

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.portfolio_boards.getro_like import (
    GetroLikePortfolioBoardSourceAdapter,
)
from core.ingestion.types import SourcePolicy


class GreycroftSourceAdapter(GetroLikePortfolioBoardSourceAdapter):
    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="greycroft",
            listing_url="https://jobs.greycroft.com/jobs",
            policy=policy,
            backend=backend,
        )


def build_greycroft_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> GreycroftSourceAdapter:
    return GreycroftSourceAdapter(policy=policy, backend=backend)

