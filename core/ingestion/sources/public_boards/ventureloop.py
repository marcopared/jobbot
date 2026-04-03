from __future__ import annotations

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.public_boards.common import UnsupportedPublicBoardSourceAdapter
from core.ingestion.types import SourcePolicy


VENTURELOOP_UNSUPPORTED_REASON = (
    "VentureLoop public-board ingestion is currently unsupported: the live search form requires site-specific query "
    "state that does not return stable listing rows from a plain public Scrapling fetch."
)


def build_ventureloop_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> UnsupportedPublicBoardSourceAdapter:
    return UnsupportedPublicBoardSourceAdapter(
        source_name="ventureloop",
        reason=VENTURELOOP_UNSUPPORTED_REASON,
        policy=policy,
        backend=backend,
    )
