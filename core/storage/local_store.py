"""Local filesystem artifact storage (EPIC 7)."""

from pathlib import Path

from core.storage.interface import ArtifactStorage, StoreResult


class LocalArtifactStorage:
    """Store artifacts on local filesystem. Applies prefix once when configured."""

    def __init__(self, root_dir: str | Path, prefix: str = "resumes"):
        self.root = Path(root_dir).resolve()
        self.prefix = (prefix or "").rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> StoreResult:
        effective_key = f"{self.prefix}/{key}" if self.prefix else key
        effective_key = str(Path(effective_key).as_posix())
        full_path = self.root / effective_key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)
        return StoreResult(
            storage_key=effective_key,
            file_url=None,
            local_path=str(full_path),
        )

    def get_local_path(self, key: str) -> Path | None:
        """key is the storage_key (as returned by store); use as-is for lookup."""
        p = self.root / Path(key).as_posix()
        return p if p.is_file() else None

    def get_signed_url(
        self,
        key: str,
        disposition: str = "attachment",
        ttl_seconds: int | None = None,
        filename: str | None = None,
    ) -> str | None:
        """Local storage serves files directly; no signed URL needed."""
        return None
