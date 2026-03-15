"""Local filesystem artifact storage (EPIC 7)."""

from pathlib import Path

from core.storage.interface import ArtifactStorage, StoreResult


class LocalArtifactStorage:
    """Store artifacts on local filesystem."""

    def __init__(self, root_dir: str | Path):
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> StoreResult:
        full_path = self.root / key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)
        rel_key = str(Path(key).as_posix())
        return StoreResult(
            storage_key=rel_key,
            file_url=None,
            local_path=str(full_path),
        )

    def get_local_path(self, key: str) -> Path | None:
        p = self.root / key
        return p if p.is_file() else None
