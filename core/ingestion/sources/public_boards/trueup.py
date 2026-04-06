from __future__ import annotations

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.public_boards.common import UnsupportedPublicBoardSourceAdapter
from core.ingestion.types import SourcePolicy


TRUEUP_UNSUPPORTED_REASON = (
    "TrueUp public-board ingestion is currently unsupported: the live jobs surface is protected by anti-bot blocking "
    "and does not expose a stable public Scrapling-friendly HTML contract."
)


def build_trueup_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> UnsupportedPublicBoardSourceAdapter:
    return UnsupportedPublicBoardSourceAdapter(
        source_name="trueup",
        reason=TRUEUP_UNSUPPORTED_REASON,
        policy=policy,
        backend=backend,
    )
