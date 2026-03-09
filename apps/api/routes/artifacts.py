from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
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


def _resolve_artifact_path(artifact: Artifact) -> Path:
    artifact_root = Path(settings.artifact_dir).resolve()
    file_path = (artifact_root / artifact.path).resolve()
    if artifact_root not in file_path.parents and file_path != artifact_root:
        raise HTTPException(status_code=400, detail="Invalid artifact path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    return file_path


@router.api_route("/{artifact_id}/download", methods=["GET", "HEAD"])
async def download_artifact(artifact_id: UUID, db: AsyncSession = Depends(get_db)):
    artifact = await _get_artifact_or_404(artifact_id, db)
    file_path = _resolve_artifact_path(artifact)
    return FileResponse(path=file_path, filename=artifact.filename, media_type="application/octet-stream")


@router.api_route("/{artifact_id}/preview", methods=["GET", "HEAD"])
async def preview_artifact(artifact_id: UUID, db: AsyncSession = Depends(get_db)):
    artifact = await _get_artifact_or_404(artifact_id, db)
    file_path = _resolve_artifact_path(artifact)
    # Inline response; browser decides rendering from media type.
    return FileResponse(path=file_path, filename=artifact.filename, content_disposition_type="inline")
