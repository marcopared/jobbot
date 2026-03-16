"""Tests for artifact preview/download routes.

Verifies provider-first retrieval: local serves from disk, gcs redirects to signed URL.
GCS mode must not serve a same-key local file when one exists on disk.
Requires Postgres with migrations applied.
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport

from apps.api.main import app
from apps.api.routes import artifacts as artifacts_module
from core.db.models import Artifact
from core.db.session import get_sync_session


def _create_artifact(path: str, filename: str) -> uuid.UUID:
    """Create an artifact record. Returns artifact_id."""
    with get_sync_session() as session:
        artifact = Artifact(
            job_id=None,
            kind="pdf",
            filename=filename,
            path=path,
        )
        session.add(artifact)
        session.flush()
        artifact_id = artifact.id
    return artifact_id


@pytest.fixture
async def client():
    """Async client for artifact route tests."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_local_provider_serves_file_response(client):
    """With provider=local and file on disk, serve FileResponse with content."""
    artifact_id = _create_artifact(path="resumes/test/file.pdf", filename="resume.pdf")

    with tempfile.TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "resumes" / "test" / "file.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"pdf-content")

        with (
            patch.object(artifacts_module.settings, "artifact_storage_provider", "local"),
            patch.object(artifacts_module.settings, "artifact_dir", tmp),
        ):
            resp = await client.get(f"/api/artifacts/{artifact_id}/download")

    assert resp.status_code == 200
    assert resp.content == b"pdf-content"
    assert "attachment" in (resp.headers.get("content-disposition") or "").lower()


@pytest.mark.asyncio
async def test_local_provider_preview_inline(client):
    """With provider=local, preview returns inline disposition."""
    artifact_id = _create_artifact(path="resumes/test/preview.pdf", filename="preview.pdf")

    with tempfile.TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "resumes" / "test" / "preview.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"pdf-preview-content")

        with (
            patch.object(artifacts_module.settings, "artifact_storage_provider", "local"),
            patch.object(artifacts_module.settings, "artifact_dir", tmp),
        ):
            resp = await client.get(f"/api/artifacts/{artifact_id}/preview")

    assert resp.status_code == 200
    assert resp.content == b"pdf-preview-content"
    assert "inline" in (resp.headers.get("content-disposition") or "").lower()


@pytest.mark.asyncio
async def test_gcs_provider_redirects_to_signed_url(client):
    """With provider=gcs, redirect to signed URL; do not probe local filesystem."""
    artifact_id = _create_artifact(path="resumes/job/file.pdf", filename="resume.pdf")

    mock_storage = MagicMock()
    mock_storage.get_signed_url.return_value = "https://storage.googleapis.com/signed-url"

    with (
        patch.object(artifacts_module.settings, "artifact_storage_provider", "gcs"),
        patch.object(artifacts_module, "get_artifact_storage", return_value=mock_storage),
    ):
        resp = await client.get(f"/api/artifacts/{artifact_id}/download")

    assert resp.status_code == 302
    assert resp.headers["location"] == "https://storage.googleapis.com/signed-url"
    mock_storage.get_signed_url.assert_called_once_with(
        key="resumes/job/file.pdf",
        disposition="attachment",
        ttl_seconds=900,
        filename="resume.pdf",
    )


@pytest.mark.asyncio
async def test_gcs_provider_does_not_serve_same_key_local_file(client):
    """With provider=gcs, do NOT serve a same-key file that exists on disk; redirect instead."""
    artifact_id = _create_artifact(path="resumes/same-key/file.pdf", filename="file.pdf")

    with tempfile.TemporaryDirectory() as tmp:
        # Create a local file at the same path - in GCS mode we must ignore it
        file_path = Path(tmp) / "resumes" / "same-key" / "file.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"local-stale-content")

        mock_storage = MagicMock()
        mock_storage.get_signed_url.return_value = "https://storage.googleapis.com/gcs-signed-url"

        with (
            patch.object(artifacts_module.settings, "artifact_storage_provider", "gcs"),
            patch.object(artifacts_module.settings, "artifact_dir", tmp),
            patch.object(artifacts_module, "get_artifact_storage", return_value=mock_storage),
        ):
            resp = await client.get(f"/api/artifacts/{artifact_id}/download")

    # Must redirect to GCS signed URL, not serve local file
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://storage.googleapis.com/gcs-signed-url"
    assert resp.content != b"local-stale-content"


@pytest.mark.asyncio
async def test_gcs_provider_preview_disposition(client):
    """With provider=gcs, preview uses inline disposition for signed URL."""
    artifact_id = _create_artifact(path="resumes/job/preview.pdf", filename="preview.pdf")

    mock_storage = MagicMock()
    mock_storage.get_signed_url.return_value = "https://storage.googleapis.com/preview-url"

    with (
        patch.object(artifacts_module.settings, "artifact_storage_provider", "gcs"),
        patch.object(artifacts_module, "get_artifact_storage", return_value=mock_storage),
    ):
        resp = await client.get(f"/api/artifacts/{artifact_id}/preview")

    assert resp.status_code == 302
    mock_storage.get_signed_url.assert_called_once_with(
        key="resumes/job/preview.pdf",
        disposition="inline",
        ttl_seconds=900,
        filename="preview.pdf",
    )


@pytest.mark.asyncio
async def test_gcs_provider_signed_url_failure_returns_503(client):
    """With provider=gcs, when signed URL generation fails, return 503, not 500."""
    artifact_id = _create_artifact(path="resumes/job/file.pdf", filename="resume.pdf")

    mock_storage = MagicMock()
    mock_storage.get_signed_url.return_value = None  # Signing failed (e.g. ADC without private key)

    with (
        patch.object(artifacts_module.settings, "artifact_storage_provider", "gcs"),
        patch.object(artifacts_module, "get_artifact_storage", return_value=mock_storage),
    ):
        download_resp = await client.get(f"/api/artifacts/{artifact_id}/download")
        preview_resp = await client.get(f"/api/artifacts/{artifact_id}/preview")

    assert download_resp.status_code == 503
    assert "sign" in download_resp.json().get("detail", "").lower()
    assert "service account" in download_resp.json().get("detail", "").lower()

    assert preview_resp.status_code == 503
    assert "sign" in preview_resp.json().get("detail", "").lower()
