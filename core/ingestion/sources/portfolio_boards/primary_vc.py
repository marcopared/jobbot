from __future__ import annotations

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.portfolio_boards.getro_like import (
    GetroLikePortfolioBoardSourceAdapter,
)
from core.ingestion.types import SourcePolicy


class PrimaryVCSourceAdapter(GetroLikePortfolioBoardSourceAdapter):
    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="primary_vc",
            listing_url="https://jobs.primary.vc/jobs",
            policy=policy,
            backend=backend,
        )


def build_primary_vc_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> PrimaryVCSourceAdapter:
    return PrimaryVCSourceAdapter(policy=policy, backend=backend)

