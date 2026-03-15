from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from apps.api.settings import Settings
from core.db.models import Artifact

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
settings = Settings()


async def _get_artifact_or_404(artifact_id: UUID, db: AsyncSession) -> Artifact:
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


def _resolve_artifact_path(artifact: Artifact) -> Path | None:
    """Return local path if artifact is stored on filesystem; None for S3."""
    artifact_root = Path(settings.artifact_dir).resolve()
    file_path = (artifact_root / artifact.path).resolve()
    if artifact_root not in file_path.parents and file_path != artifact_root:
        return None
    return file_path if file_path.is_file() else None


@router.api_route("/{artifact_id}/download", methods=["GET", "HEAD"])
async def download_artifact(artifact_id: UUID, db: AsyncSession = Depends(get_db)):
    artifact = await _get_artifact_or_404(artifact_id, db)
    if artifact.file_url:
        return RedirectResponse(url=artifact.file_url, status_code=302)
    file_path = _resolve_artifact_path(artifact)
    if not file_path:
        raise HTTPException(status_code=404, detail="Artifact file not found")
    return FileResponse(path=file_path, filename=artifact.filename, media_type="application/octet-stream")


@router.api_route("/{artifact_id}/preview", methods=["GET", "HEAD"])
async def preview_artifact(artifact_id: UUID, db: AsyncSession = Depends(get_db)):
    artifact = await _get_artifact_or_404(artifact_id, db)
    if artifact.file_url:
        return RedirectResponse(url=artifact.file_url, status_code=302)
    file_path = _resolve_artifact_path(artifact)
    if not file_path:
        raise HTTPException(status_code=404, detail="Artifact file not found")
    return FileResponse(path=file_path, filename=artifact.filename, content_disposition_type="inline")
