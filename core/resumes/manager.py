import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from apps.api.settings import Settings
from core.db.models import Artifact, ArtifactKind, Job
from core.resumes.parser import extract_text_from_pdf
from core.resumes.tailor import tailor_resume

logger = logging.getLogger(__name__)
settings = Settings()


def _load_master_skills(path: str) -> list[str]:
    skills_path = Path(path)
    if not skills_path.is_file():
        return []
    try:
        data = json.loads(skills_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(item) for item in data]
    except Exception:
        logger.warning("Failed to load master skills from %s", path)
    return []


def prepare_resume(session, job_id: UUID) -> Artifact | None:
    """
    Prepare resume artifact for a job.
    Tailoring is attempted when enabled + ATS data exists, otherwise copy base resume.
    Returns created Artifact or None when base resume is missing.
    """
    job = session.get(Job, job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    base_resume = Path(settings.base_resume_path)
    if not base_resume.is_file():
        logger.warning("Base resume not found at %s; skipping resume prep", base_resume)
        return None

    artifact_root = Path(settings.artifact_dir)
    job_dir = artifact_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    tailored = False
    output_filename = f"resume_{timestamp}.pdf"
    output_path = job_dir / output_filename

    if settings.resume_tailor_enabled and job.ats_match_breakdown_json:
        try:
            resume_text = extract_text_from_pdf(str(base_resume))
            master_skills = _load_master_skills(settings.master_skills_path)
            tailored_text = tailor_resume(
                resume_text=resume_text,
                ats_breakdown=job.ats_match_breakdown_json,
                master_skills=master_skills,
                job_description=job.description or "",
            )
            output_filename = f"tailored_resume_{timestamp}.pdf"
            output_path = job_dir / output_filename
            # V1 pragmatic path: keep .pdf extension but persist tailored text content.
            output_path.write_text(tailored_text, encoding="utf-8")
            tailored = True
        except Exception:
            logger.warning(
                "Resume tailoring failed for job %s; falling back to base copy",
                job_id,
            )

    if not tailored:
        shutil.copy2(base_resume, output_path)

    artifact = Artifact(
        job_id=job_id,
        kind=ArtifactKind.PDF.value,
        filename=output_filename,
        path=str(output_path.relative_to(artifact_root)),
        size_bytes=output_path.stat().st_size,
        meta_json={"tailored": tailored, "ats_match_score": job.ats_match_score},
    )
    session.add(artifact)
    session.flush()
    return artifact
