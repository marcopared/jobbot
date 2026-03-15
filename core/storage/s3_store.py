"""S3 artifact storage (EPIC 7)."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from core.storage.interface import ArtifactStorage, StoreResult

if TYPE_CHECKING:
    import boto3

logger = logging.getLogger(__name__)


class S3ArtifactStorage:
    """Store artifacts in AWS S3."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "resumes",
        region: str | None = None,
    ):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.region = region

    def store(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> StoreResult:
        try:
            import boto3
        except ImportError:
            raise RuntimeError("boto3 required for S3 storage") from None

        s3_key = f"{self.prefix}/{key}" if self.prefix else key
        client = boto3.client("s3", region_name=self.region)
        client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=data,
            ContentType=content_type,
        )
        url = f"https://{self.bucket}.s3.amazonaws.com/{s3_key}"
        if self.region:
            url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{s3_key}"
        return StoreResult(
            storage_key=s3_key,
            file_url=url,
            local_path=None,
        )

    def get_local_path(self, key: str) -> Path | None:
        return None
