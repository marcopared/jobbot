from __future__ import annotations

from core.ingestion.registry import build_default_source_registry


def test_ventureloop_adapter_is_registered_and_explicitly_unsupported():
    adapter = build_default_source_registry().create("ventureloop")

    batch = adapter.acquire()

    assert batch.records == []
    assert batch.error is not None
    assert "unsupported" in batch.error.lower()
    assert batch.metadata["source_name"] == "ventureloop"
