from __future__ import annotations

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.public_boards.common import UnsupportedPublicBoardSourceAdapter
from core.ingestion.types import SourcePolicy


UNDERDOG_UNSUPPORTED_REASON = (
    "Underdog public-board ingestion is currently unsupported: the public jobs surface is a marketing shell that links "
    "to a separate board and does not expose stable public listing records in the initial HTML response."
)


def build_underdog_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> UnsupportedPublicBoardSourceAdapter:
    return UnsupportedPublicBoardSourceAdapter(
        source_name="underdog",
        reason=UNDERDOG_UNSUPPORTED_REASON,
        policy=policy,
        backend=backend,
    )
