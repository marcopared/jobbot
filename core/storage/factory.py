"""Factory for artifact storage backend (EPIC 7)."""

from apps.api.settings import Settings

from core.storage.gcs_store import GCSArtifactStorage
from core.storage.interface import ArtifactStorage
from core.storage.local_store import LocalArtifactStorage


def get_artifact_storage(
    artifact_dir: str | None = None,
    artifact_storage_provider: str | None = None,
    gcs_artifact_bucket: str | None = None,
    gcs_project_id: str | None = None,
    gcs_prefix: str | None = None,
    gcs_signed_url_ttl_seconds: int | None = None,
) -> ArtifactStorage:
    """
    Return GCS storage when provider is 'gcs' and bucket is configured;
    otherwise local filesystem fallback.
    """
    settings = Settings()
    provider = artifact_storage_provider or settings.artifact_storage_provider
    bucket = gcs_artifact_bucket or settings.gcs_artifact_bucket
    prefix = gcs_prefix if gcs_prefix is not None else settings.gcs_prefix
    root_dir = artifact_dir or settings.artifact_dir

    if provider == "gcs" and bucket:
        return GCSArtifactStorage(
            bucket=bucket,
            prefix=prefix,
            project_id=gcs_project_id or settings.gcs_project_id,
            signed_url_ttl_seconds=gcs_signed_url_ttl_seconds
            or settings.gcs_signed_url_ttl_seconds,
        )
    return LocalArtifactStorage(root_dir=root_dir, prefix=prefix)
