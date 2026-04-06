"""Local-first evidence assembly for resume-generation v2."""

from __future__ import annotations

from pathlib import Path

from apps.api.settings import Settings
from core.db.models import Job
from core.inventory.loader import compute_inventory_hash, load_inventory
from core.inventory.types import ExperienceInventory
from core.resumes._serialization import canonical_json_hash
from core.resumes.evidence_types import (
    ResumeEvidenceItem,
    ResumeEvidencePackage,
    ResumeEvidenceSource,
)
from core.resumes.local_inputs import (
    SUPPORTED_INPUT_EXTENSIONS,
    find_optional_input_file,
    list_supported_input_files,
    load_local_input_document,
)
from core.resumes.v2_pipeline import build_inventory_evidence_package

settings = Settings()

OPTIONAL_SOURCE_NAMES = (
    "current_resume",
    "current_role",
    "achievements",
    "project_writeups",
)


def build_resume_evidence_package(
    job: Job,
    *,
    inventory_path: str | Path | None = None,
    inputs_dir: str | Path | None = None,
) -> ResumeEvidencePackage:
    """Assemble a deterministic evidence package from local user-side sources."""
    inventory_file = Path(inventory_path or settings.experience_inventory_path)
    inputs_root = Path(inputs_dir or settings.resume_inputs_dir)

    inventory: ExperienceInventory = load_inventory(inventory_file)
    inventory_hash = compute_inventory_hash(inventory)
    base_package = build_inventory_evidence_package(inventory, inventory_hash)

    source_metadata: list[ResumeEvidenceSource] = []
    source_metadata.append(
        ResumeEvidenceSource(
            source_name="inventory",
            required=True,
            present=True,
            source_kind="file",
            format=inventory_file.suffix.lstrip("."),
            path=str(inventory_file),
            content_hash=inventory_hash,
            item_count=len(base_package.items),
            used_for_facts=True,
            used_for_targeting=False,
        )
    )

    job_description = (job.description or "").strip()
    job_description_hash = (
        canonical_json_hash({"description": job_description}, length=32)
        if job_description
        else None
    )
    source_metadata.append(
        ResumeEvidenceSource(
            source_name="target_job_description",
            required=True,
            present=bool(job_description),
            source_kind="job_field",
            format="text",
            path=None,
            content_hash=job_description_hash,
            item_count=0,
            used_for_facts=False,
            used_for_targeting=True,
            notes=() if job_description else ("job.description is empty",),
            metadata=tuple(
                sorted(
                    (
                        ("job_title", job.title or ""),
                        ("company_name", job.company_name_raw or ""),
                    )
                )
            ),
        )
    )

    extra_items: list[ResumeEvidenceItem] = []

    for source_name in ("current_resume", "current_role", "achievements"):
        path = find_optional_input_file(inputs_root, source_name)
        if path is None:
            source_metadata.append(
                ResumeEvidenceSource(
                    source_name=source_name,
                    required=False,
                    present=False,
                    source_kind="file",
                    format=None,
                    path=str(inputs_root / source_name),
                    content_hash=None,
                    item_count=0,
                    used_for_facts=True,
                    used_for_targeting=False,
                    notes=(
                        "optional source not found",
                        f"supported extensions: {','.join(SUPPORTED_INPUT_EXTENSIONS)}",
                    ),
                )
            )
            continue
        document = load_local_input_document(path)
        for index, record in enumerate(document.records):
            extra_items.append(
                ResumeEvidenceItem(
                    id=f"{source_name}:{index}",
                    source_type=source_name,
                    item_type="supplemental_text",
                    text=record.text,
                    tags=record.tags,
                    metrics=record.metrics,
                    parent_id=source_name,
                    attributes=record.attributes
                    + (("path", str(document.path)), ("format", document.format)),
                )
            )
        source_metadata.append(
            ResumeEvidenceSource(
                source_name=source_name,
                required=False,
                present=True,
                source_kind="file",
                format=document.format,
                path=str(document.path),
                content_hash=document.content_hash,
                item_count=len(document.records),
                used_for_facts=True,
                used_for_targeting=False,
            )
        )

    project_dir = inputs_root / "projects"
    project_file = find_optional_input_file(inputs_root, "projects")
    if project_dir.exists() and project_file is not None:
        raise ValueError(
            f"Ambiguous project writeups input: both {project_dir} and {project_file} exist"
        )
    project_files = list_supported_input_files(project_dir) if project_dir.is_dir() else ()
    if project_file is not None:
        project_files = (project_file,)

    if not project_files:
        source_metadata.append(
            ResumeEvidenceSource(
                source_name="project_writeups",
                required=False,
                present=False,
                source_kind="directory",
                format=None,
                path=str(project_dir),
                content_hash=None,
                item_count=0,
                used_for_facts=True,
                used_for_targeting=False,
                notes=("optional source not found",),
            )
        )
    else:
        project_hashes: list[str] = []
        project_item_count = 0
        for file_index, path in enumerate(project_files):
            document = load_local_input_document(path)
            project_hashes.append(document.content_hash)
            for record_index, record in enumerate(document.records):
                extra_items.append(
                    ResumeEvidenceItem(
                        id=f"project_writeups:{file_index}:{record_index}",
                        source_type="project_writeups",
                        item_type="supplemental_text",
                        text=record.text,
                        tags=record.tags,
                        metrics=record.metrics,
                        parent_id=path.stem,
                        attributes=record.attributes
                        + (("path", str(document.path)), ("format", document.format)),
                    )
                )
            project_item_count += len(document.records)
        source_metadata.append(
            ResumeEvidenceSource(
                source_name="project_writeups",
                required=False,
                present=True,
                source_kind="directory" if project_dir.is_dir() else "file",
                format="multi" if len(project_files) > 1 else project_files[0].suffix.lstrip("."),
                path=str(project_dir if project_dir.is_dir() else project_files[0]),
                content_hash=canonical_json_hash(
                    {"files": project_hashes, "count": len(project_files)},
                    length=32,
                ),
                item_count=project_item_count,
                used_for_facts=True,
                used_for_targeting=False,
                metadata=(("file_count", str(len(project_files))),),
            )
        )

    sorted_source_metadata = tuple(
        sorted(source_metadata, key=lambda source: source.source_name)
    )
    inputs_hash = canonical_json_hash(
        {
            "inventory_version_hash": base_package.inventory_version_hash,
            "sources": [
                {
                    "source_name": source.source_name,
                    "required": source.required,
                    "present": source.present,
                    "source_kind": source.source_kind,
                    "format": source.format,
                    "content_hash": source.content_hash,
                    "item_count": source.item_count,
                    "used_for_facts": source.used_for_facts,
                    "used_for_targeting": source.used_for_targeting,
                    "notes": list(source.notes),
                }
                for source in sorted_source_metadata
            ],
        }
    )
    missing_optional_sources = tuple(
        source.source_name
        for source in sorted_source_metadata
        if not source.required and not source.present
    )
    source_kind = (
        "inventory-only"
        if not [source for source in sorted_source_metadata if source.source_name in OPTIONAL_SOURCE_NAMES and source.present]
        else "inventory-plus-local-files"
    )

    return ResumeEvidencePackage(
        contact=base_package.contact,
        summary_variants=base_package.summary_variants,
        skills=base_package.skills,
        education=base_package.education,
        roles=base_package.roles,
        projects=base_package.projects,
        items=base_package.items + tuple(extra_items),
        source_metadata=sorted_source_metadata,
        missing_optional_sources=missing_optional_sources,
        inputs_hash=inputs_hash,
        inventory_version_hash=base_package.inventory_version_hash,
        source_kind=source_kind,
    )
