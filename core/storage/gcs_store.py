"""GCS artifact storage (EPIC 7).

Store artifacts in Google Cloud Storage. Objects remain private; serve via signed URLs on demand.
Requires Application Default Credentials. For signed URL generation, credentials must have a private key
(e.g. GOOGLE_APPLICATION_CREDENTIALS pointing to a service account JSON key). User credentials from
`gcloud auth application-default login` cannot sign URLs.
"""

import logging
from pathlib import Path

from core.storage.interface import ArtifactStorage, StoreResult

logger = logging.getLogger(__name__)


class GCSArtifactStorage:
    """Store artifacts in Google Cloud Storage."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "resumes",
        project_id: str | None = None,
        signed_url_ttl_seconds: int = 900,
    ):
        self.bucket_name = bucket
        self.prefix = (prefix or "").rstrip("/")
        self.project_id = project_id
        self.signed_url_ttl_seconds = signed_url_ttl_seconds

    def store(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> StoreResult:
        try:
            from google.cloud import storage
        except ImportError:
            raise RuntimeError("google-cloud-storage required for GCS storage") from None

        gcs_key = f"{self.prefix}/{key}" if self.prefix else key
        client = storage.Client(project=self.project_id)
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(gcs_key)
        blob.upload_from_string(data, content_type=content_type)
        return StoreResult(
            storage_key=gcs_key,
            file_url=None,  # Do not persist URL; generate signed URL on demand.
            local_path=None,
        )

    def get_local_path(self, key: str) -> Path | None:
        return None

    def get_signed_url(
        self,
        key: str,
        disposition: str = "attachment",
        ttl_seconds: int | None = None,
        filename: str | None = None,
    ) -> str | None:
        """Generate a signed URL for the object. Returns None on failure."""
        try:
            from google.cloud import storage
        except ImportError:
            logger.warning("google-cloud-storage not available; cannot generate signed URL")
            return None

        ttl = ttl_seconds if ttl_seconds is not None else self.signed_url_ttl_seconds
        expiration_seconds = min(ttl, 604800)  # GCS max 7 days

        client = storage.Client(project=self.project_id)
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(key)

        params: dict = {}
        if disposition == "attachment" and filename:
            params["response_disposition"] = f'attachment; filename="{filename}"'
        elif disposition == "inline":
            params["response_disposition"] = "inline"

        try:
            url = blob.generate_signed_url(
                version="v4",
                expiration=expiration_seconds,
                method="GET",
                **params,
            )
            return url
        except Exception as e:
            logger.warning(
                "GCS signed URL generation failed: %s (bucket=%s key=%s)",
                e,
                self.bucket_name,
                key,
                exc_info=True,
            )
            return None
