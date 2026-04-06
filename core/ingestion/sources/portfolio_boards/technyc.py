from __future__ import annotations

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.portfolio_boards.getro_like import (
    GetroLikePortfolioBoardSourceAdapter,
)
from core.ingestion.types import SourcePolicy


class TechNYCSourceAdapter(GetroLikePortfolioBoardSourceAdapter):
    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="technyc",
            listing_url="https://jobs.technyc.org/jobs",
            policy=policy,
            backend=backend,
        )


def build_technyc_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> TechNYCSourceAdapter:
    return TechNYCSourceAdapter(policy=policy, backend=backend)

