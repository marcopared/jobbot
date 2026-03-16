"""Tests for artifact storage key conventions (local and GCS).

Verifies:
- Producers pass relative keys; backends apply prefix exactly once.
- No resumes/resumes/ duplication.
- Local and GCS storage_key semantics for preview/download routes.
- Signed URL generation behavior (mocked for GCS).
- GCS mode requires google-cloud-storage (no boto3 in storage path).
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.storage.factory import get_artifact_storage
from core.storage.gcs_store import GCSArtifactStorage
from core.storage.local_store import LocalArtifactStorage


# --- Local storage ---


def test_local_storage_applies_prefix_once():
    """Local store applies resumes/ prefix once; storage_key has no duplication."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStorage(root_dir=tmp, prefix="resumes")
        relative_key = f"{uuid.uuid4()}/20250101_120000_resume.pdf"
        result = store.store(key=relative_key, data=b"test", content_type="application/pdf")

        assert "resumes/resumes/" not in result.storage_key
        assert result.storage_key == f"resumes/{relative_key}"
        assert (Path(tmp) / result.storage_key).is_file()


def test_local_storage_key_retrieval():
    """Artifact.path (storage_key) resolves to correct local file."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStorage(root_dir=tmp, prefix="resumes")
        job_id = uuid.uuid4()
        relative_key = f"{job_id}/20250101_120000_resume.pdf"
        store.store(key=relative_key, data=b"pdf-content", content_type="application/pdf")

        storage_key = f"resumes/{relative_key}"
        local_path = store.get_local_path(storage_key)
        assert local_path is not None
        assert local_path.read_bytes() == b"pdf-content"


def test_local_storage_without_prefix():
    """Local store with empty prefix stores at root directly."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStorage(root_dir=tmp, prefix="")
        relative_key = f"{uuid.uuid4()}/20250101_120000_resume.pdf"
        result = store.store(key=relative_key, data=b"test", content_type="application/pdf")

        assert result.storage_key == relative_key
        assert (Path(tmp) / relative_key).is_file()


def test_local_storage_get_signed_url_returns_none():
    """Local storage returns None for get_signed_url (serve from disk)."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStorage(root_dir=tmp, prefix="resumes")
        assert store.get_signed_url(key="resumes/job/file.pdf") is None


# --- Dependencies ---


def test_google_cloud_storage_available():
    """GCS mode requires google-cloud-storage; verify it is importable."""
    pytest.importorskip("google.cloud.storage")
    from google.cloud import storage  # noqa: F401
    assert storage is not None


# --- GCS storage ---


def test_gcs_storage_no_prefix_duplication():
    """GCS store applies prefix once; blob key must not contain resumes/resumes/."""
    with patch("google.cloud.storage.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        store = GCSArtifactStorage(bucket="my-bucket", prefix="resumes")
        relative_key = f"{uuid.uuid4()}/20250101_120000_resume.pdf"
        result = store.store(key=relative_key, data=b"test", content_type="application/pdf")

        mock_blob.upload_from_string.assert_called_once_with(b"test", content_type="application/pdf")
        blob_key = mock_bucket.blob.call_args[0][0]
        assert "resumes/resumes/" not in blob_key
        assert blob_key == f"resumes/{relative_key}"
        assert result.storage_key == blob_key


def test_gcs_storage_key_convention():
    """GCS storage_key is prefix + relative_key, exactly one prefix."""
    with patch("google.cloud.storage.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        store = GCSArtifactStorage(bucket="bucket", prefix="resumes")
        job_id = uuid.uuid4()
        relative_key = f"{job_id}/20250101_120000_resume.pdf"
        result = store.store(key=relative_key, data=b"x", content_type="application/pdf")

        expected_key = f"resumes/{job_id}/20250101_120000_resume.pdf"
        assert result.storage_key == expected_key
        assert mock_bucket.blob.call_args[0][0] == expected_key


def test_gcs_get_signed_url_mocked():
    """GCS store generates signed URL via generate_signed_url."""
    with patch("google.cloud.storage.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        mock_bucket.blob.return_value = mock_blob

        store = GCSArtifactStorage(bucket="bucket", prefix="resumes", signed_url_ttl_seconds=900)
        url = store.get_signed_url(key="resumes/job/file.pdf", disposition="attachment")
        assert url == "https://storage.googleapis.com/signed-url"
        mock_blob.generate_signed_url.assert_called_once()
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert call_kwargs["version"] == "v4"
        assert call_kwargs["expiration"] == 900
        assert call_kwargs["method"] == "GET"


def test_gcs_get_signed_url_returns_none_on_runtime_error():
    """GCS store returns None (not raises) when generate_signed_url fails (e.g. ADC without private key)."""
    with patch("google.cloud.storage.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.side_effect = Exception("Credentials cannot sign URLs")
        mock_bucket.blob.return_value = mock_blob

        store = GCSArtifactStorage(bucket="bucket", prefix="resumes")
        url = store.get_signed_url(key="resumes/job/file.pdf", disposition="attachment")
        assert url is None


def test_gcs_get_signed_url_with_filename():
    """GCS store includes response_disposition when filename provided."""
    with patch("google.cloud.storage.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed"
        mock_bucket.blob.return_value = mock_blob

        store = GCSArtifactStorage(bucket="bucket", prefix="resumes")
        store.get_signed_url(key="resumes/job/file.pdf", disposition="attachment", filename="resume.pdf")
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert "response_disposition" in call_kwargs
        assert 'filename="resume.pdf"' in call_kwargs["response_disposition"]


# --- Factory ---


def test_factory_local_uses_prefix():
    """Factory returns LocalArtifactStorage when provider is local (default)."""
    with tempfile.TemporaryDirectory() as tmp:
        storage = get_artifact_storage(artifact_dir=tmp)
        assert isinstance(storage, LocalArtifactStorage)
        assert storage.prefix == "resumes"

        relative_key = f"{uuid.uuid4()}/20250101_120000_resume.pdf"
        result = storage.store(key=relative_key, data=b"x", content_type="application/pdf")
        assert result.storage_key.startswith("resumes/")
        assert "resumes/resumes/" not in result.storage_key


def test_factory_gcs_when_provider_and_bucket_configured():
    """Factory returns GCSArtifactStorage when provider=gcs and bucket set."""
    with patch.dict("os.environ", {}, clear=False):
        storage = get_artifact_storage(
            artifact_dir="/tmp/art",
            artifact_storage_provider="gcs",
            gcs_artifact_bucket="my-gcs-bucket",
        )
        assert isinstance(storage, GCSArtifactStorage)
        assert storage.bucket_name == "my-gcs-bucket"
        assert storage.prefix == "resumes"
