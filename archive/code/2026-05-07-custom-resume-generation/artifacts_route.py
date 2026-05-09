from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from apps.api.settings import Settings
from core.db.models import Artifact
from core.storage.factory import get_artifact_storage

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
settings = Settings()


async def _get_artifact_or_404(artifact_id: UUID, db: AsyncSession) -> Artifact:
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


def _resolve_artifact_path(artifact: Artifact) -> Path | None:
    """Return local path if artifact is stored on filesystem; None if not local or not found."""
    artifact_root = Path(settings.artifact_dir).resolve()
    file_path = (artifact_root / artifact.path).resolve()
    if artifact_root not in file_path.parents and file_path != artifact_root:
        return None
    return file_path if file_path.is_file() else None


def _get_signed_url_for_gcs(artifact: Artifact, disposition: str) -> str | None:
    """Generate signed URL for GCS-backed artifact. Returns None on failure."""
    storage = get_artifact_storage()
    return storage.get_signed_url(
        key=artifact.path,
        disposition=disposition,
        ttl_seconds=settings.gcs_signed_url_ttl_seconds,
        filename=artifact.filename,
    )


def _serve_artifact_download(artifact: Artifact):
    """Provider-first retrieval for download. Returns response or raises HTTPException."""
    provider = settings.artifact_storage_provider
    if provider == "local":
        file_path = _resolve_artifact_path(artifact)
        if file_path:
            return FileResponse(
                path=file_path,
                filename=artifact.filename,
                media_type="application/octet-stream",
            )
    elif provider == "gcs":
        signed_url = _get_signed_url_for_gcs(artifact, disposition="attachment")
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=302)
        raise HTTPException(
            status_code=503,
            detail="Artifact download unavailable: storage credentials cannot sign URLs. Configure a service account with a private key (e.g. GOOGLE_APPLICATION_CREDENTIALS) for signed URL generation.",
        )
    if artifact.file_url:
        return RedirectResponse(url=artifact.file_url, status_code=302)
    raise HTTPException(status_code=404, detail="Artifact file not found")


def _serve_artifact_preview(artifact: Artifact):
    """Provider-first retrieval for preview. Returns response or raises HTTPException."""
    provider = settings.artifact_storage_provider
    if provider == "local":
        file_path = _resolve_artifact_path(artifact)
        if file_path:
            return FileResponse(
                path=file_path,
                filename=artifact.filename,
                content_disposition_type="inline",
            )
    elif provider == "gcs":
        signed_url = _get_signed_url_for_gcs(artifact, disposition="inline")
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=302)
        raise HTTPException(
            status_code=503,
            detail="Artifact preview unavailable: storage credentials cannot sign URLs. Configure a service account with a private key (e.g. GOOGLE_APPLICATION_CREDENTIALS) for signed URL generation.",
        )
    if artifact.file_url:
        return RedirectResponse(url=artifact.file_url, status_code=302)
    raise HTTPException(status_code=404, detail="Artifact file not found")


@router.api_route("/{artifact_id}/download", methods=["GET", "HEAD"])
async def download_artifact(artifact_id: UUID, db: AsyncSession = Depends(get_db)):
    artifact = await _get_artifact_or_404(artifact_id, db)
    return _serve_artifact_download(artifact)


@router.api_route("/{artifact_id}/preview", methods=["GET", "HEAD"])
async def preview_artifact(artifact_id: UUID, db: AsyncSession = Depends(get_db)):
    artifact = await _get_artifact_or_404(artifact_id, db)
    return _serve_artifact_preview(artifact)
