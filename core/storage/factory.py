"""Factory for artifact storage backend (EPIC 7)."""

import os

from core.storage.interface import ArtifactStorage
from core.storage.local_store import LocalArtifactStorage
from core.storage.s3_store import S3ArtifactStorage


def get_artifact_storage(
    artifact_dir: str,
    s3_bucket: str | None = None,
    s3_prefix: str = "resumes",
    s3_region: str | None = None,
) -> ArtifactStorage:
    """
    Return S3 storage when bucket configured and credentials present;
    otherwise local filesystem fallback.
    """
    bucket = s3_bucket or os.environ.get("AWS_S3_ARTIFACT_BUCKET")
    if bucket and _has_aws_credentials():
        return S3ArtifactStorage(
            bucket=bucket,
            prefix=s3_prefix,
            region=s3_region or os.environ.get("AWS_REGION"),
        )
    return LocalArtifactStorage(root_dir=artifact_dir)


def _has_aws_credentials() -> bool:
    return bool(
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("AWS_PROFILE")
        or os.environ.get("AWS_ROLE_ARN")
    )
