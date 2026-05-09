"""Shared metadata helpers for resume-generation artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from core.db.models import JobAnalysis
    from core.resumes.evidence_types import ResumeEvidencePackage
    from core.resumes.layout_types import FitDiagnostics, FitResult, LayoutPlan
    from core.resumes.payload_types import ResumePayloadV2


RESUME_ARTIFACT_ROLE_PRIMARY = "resume_pdf_primary"
RESUME_ARTIFACT_ROLE_PAYLOAD = "resume_payload"
RESUME_ARTIFACT_ROLE_DIAGNOSTICS = "resume_diagnostics"


def get_resume_artifact_role(meta_json: dict[str, Any] | None) -> str | None:
    """Return the logical resume artifact role recorded in metadata."""
    if not isinstance(meta_json, dict):
        return None
    role = meta_json.get("artifact_role")
    return str(role) if isinstance(role, str) and role.strip() else None


def is_primary_resume_artifact(kind: str | None, meta_json: dict[str, Any] | None) -> bool:
    """Treat legacy PDFs as primary resume artifacts when no explicit role exists."""
    role = get_resume_artifact_role(meta_json)
    if role:
        return role == RESUME_ARTIFACT_ROLE_PRIMARY
    return (kind or "").lower() == "pdf"


def build_evidence_completeness_summary(
    *,
    source_kind: str | None,
    source_metadata: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    missing_optional_sources: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    """Build a compact evidence completeness summary for read models and sidecars."""
    metadata = [
        item for item in (source_metadata or []) if isinstance(item, dict)
    ]
    missing_optional = [
        str(item) for item in (missing_optional_sources or []) if str(item).strip()
    ]

    total_sources = len(metadata)
    present_sources = sum(1 for item in metadata if bool(item.get("present")))
    required_sources = [item for item in metadata if bool(item.get("required"))]
    required_present = sum(1 for item in required_sources if bool(item.get("present")))
    optional_total = total_sources - len(required_sources)
    optional_present = present_sources - required_present

    parts: list[str] = []
    if source_kind == "inventory-only":
        parts.append("Inventory-only evidence")
    if required_sources:
        parts.append(f"required {required_present}/{len(required_sources)} present")
    if optional_total:
        parts.append(f"optional {optional_present}/{optional_total} present")
    if missing_optional:
        parts.append(f"missing {', '.join(missing_optional)}")
    summary = "; ".join(parts) if parts else "Evidence summary unavailable"

    return {
        "summary": summary,
        "source_kind": source_kind,
        "total_sources": total_sources,
        "present_sources": present_sources,
        "required_sources": len(required_sources),
        "required_present": required_present,
        "optional_sources": optional_total,
        "optional_present": optional_present,
        "missing_optional_sources": missing_optional,
    }


def build_source_metadata_summary(
    evidence_package: "ResumeEvidencePackage",
) -> list[dict[str, object]]:
    """Flatten evidence source metadata for artifact payloads and manifests."""
    return [
        {
            "source_name": source.source_name,
            "required": source.required,
            "present": source.present,
            "source_kind": source.source_kind,
            "format": source.format,
            "item_count": source.item_count,
            "used_for_facts": source.used_for_facts,
            "used_for_targeting": source.used_for_targeting,
            "used_for_preferences": source.used_for_preferences,
        }
        for source in evidence_package.source_metadata
    ]


def build_resume_v2_metadata(
    *,
    evidence_package: "ResumeEvidencePackage",
    payload: "ResumePayloadV2",
    fit_result: "FitResult",
    layout_plan: "LayoutPlan",
    fit_diagnostics: "FitDiagnostics",
    fit_outcome: str,
) -> dict[str, object]:
    """Build the shared resume-v2 metadata envelope carried by artifacts and sidecars."""
    source_metadata = build_source_metadata_summary(evidence_package)
    missing_optional_sources = list(evidence_package.missing_optional_sources)
    evidence_completeness = build_evidence_completeness_summary(
        source_kind=evidence_package.source_kind,
        source_metadata=source_metadata,
        missing_optional_sources=missing_optional_sources,
    )
    return {
        "evidence_schema_version": evidence_package.schema_version,
        "payload_schema_version": payload.schema_version,
        "fit_schema_version": fit_result.schema_version,
        "layout_schema_version": layout_plan.schema_version,
        "fit_diagnostics_schema_version": fit_diagnostics.schema_version,
        "source_kind": evidence_package.source_kind,
        "inputs_hash": evidence_package.inputs_hash,
        "evidence_hash": evidence_package.compute_hash(),
        "fit_hash": fit_result.compute_hash(),
        "payload_hash": payload.compute_hash(),
        "layout_hash": layout_plan.compute_hash(),
        "effective_input_hash": payload.effective_input_hash,
        "fit_outcome": fit_outcome,
        "fit_diagnostics": fit_diagnostics.to_dict(),
        "missing_optional_sources": missing_optional_sources,
        "source_metadata": source_metadata,
        "evidence_completeness": evidence_completeness,
    }


def build_resume_sidecar_documents(
    *,
    job_id: UUID,
    persona: str,
    generated_at: datetime,
    artifact_bundle_id: str,
    analysis: "JobAnalysis | None",
    evidence_package: "ResumeEvidencePackage",
    payload: "ResumePayloadV2",
    fit_result: "FitResult",
    layout_plan: "LayoutPlan",
    fit_diagnostics: "FitDiagnostics",
    fit_outcome: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Build the common metadata plus payload/diagnostics sidecar documents."""
    resume_v2 = build_resume_v2_metadata(
        evidence_package=evidence_package,
        payload=payload,
        fit_result=fit_result,
        layout_plan=layout_plan,
        fit_diagnostics=fit_diagnostics,
        fit_outcome=fit_outcome,
    )
    common_meta = {
        "artifact_bundle_id": artifact_bundle_id,
        "generated_at": generated_at.isoformat(),
        "grounded": True,
        "persona": persona,
        "ats_compatibility_score": analysis.ats_compatibility_score if analysis else None,
        "resume_v2": resume_v2,
    }
    payload_document = {
        "schema_version": "resume-payload-sidecar-v1",
        "job_id": str(job_id),
        "persona": persona,
        "generated_at": generated_at.isoformat(),
        "artifact_bundle_id": artifact_bundle_id,
        "inputs_hash": evidence_package.inputs_hash,
        "payload_hash": payload.compute_hash(),
        "payload": payload.to_dict(),
    }
    diagnostics_document = {
        "schema_version": "resume-diagnostics-sidecar-v1",
        "job_id": str(job_id),
        "persona": persona,
        "generated_at": generated_at.isoformat(),
        "artifact_bundle_id": artifact_bundle_id,
        "fit_outcome": fit_outcome,
        "resume_v2": resume_v2,
    }
    return common_meta, payload_document, diagnostics_document


def extract_resume_artifact_summary(meta_json: dict[str, Any] | None) -> dict[str, Any]:
    """Extract optional resume-v2 summary fields from artifact metadata."""
    if not isinstance(meta_json, dict):
        return {}

    resume_v2 = meta_json.get("resume_v2")
    if not isinstance(resume_v2, dict):
        return {
            "artifact_role": get_resume_artifact_role(meta_json),
            "is_primary": is_primary_resume_artifact(None, meta_json),
        }

    evidence_completeness = resume_v2.get("evidence_completeness")
    if not isinstance(evidence_completeness, dict):
        evidence_completeness = build_evidence_completeness_summary(
            source_kind=resume_v2.get("source_kind"),
            source_metadata=resume_v2.get("source_metadata"),
            missing_optional_sources=resume_v2.get("missing_optional_sources"),
        )

    return {
        "artifact_role": get_resume_artifact_role(meta_json),
        "is_primary": is_primary_resume_artifact(None, meta_json),
        "payload_version": resume_v2.get("payload_schema_version"),
        "inputs_hash": resume_v2.get("inputs_hash"),
        "fit_status": resume_v2.get("fit_outcome"),
        "evidence_completeness": evidence_completeness,
    }
