"""Fixture-backed verification harness for resume-generation v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from core.db.models import Job, JobAnalysis
from core.resumes._serialization import canonical_json_dumps
from core.resumes.artifact_metadata import build_resume_sidecar_documents
from core.resumes.evidence_builder import build_resume_evidence_package
from core.resumes.fit_planner import plan_resume_artifacts
from core.resumes.html_template import TEMPLATE_VERSION, render_html
from core.resumes.layout_types import FIT_OUTCOME_SUCCESS_ONE_PAGE
from core.resumes.pdf_renderer import count_pdf_pages, render_html_to_pdf_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "resume_verification"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "storage" / "verification" / "resume_v2_demo"
DEMO_GENERATED_AT = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
MANIFEST_SCHEMA_VERSION = "resume-v2-demo-manifest-v1"


@dataclass(frozen=True)
class ResumeVerificationCase:
    """Fixture-backed local verification case for a deterministic resume-v2 demo."""

    case_id: str
    label: str
    job_title: str
    company_name: str
    description: str
    persona: str
    target_keywords: tuple[str, ...]
    found_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    inventory_path: Path
    inputs_dir: Path
    golden_payload_path: Path


def _read_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_verification_cases(fixtures_root: Path = FIXTURES_ROOT) -> tuple[ResumeVerificationCase, ...]:
    """Load the bounded resume-v2 verification fixture set."""
    cases: list[ResumeVerificationCase] = []
    for fixture_path in sorted(fixtures_root.glob("*.json")):
        data = _read_fixture(fixture_path)
        cases.append(
            ResumeVerificationCase(
                case_id=str(data["case_id"]),
                label=str(data["label"]),
                job_title=str(data["job_title"]),
                company_name=str(data["company_name"]),
                description=str(data["description"]),
                persona=str(data["persona"]),
                target_keywords=tuple(str(item).lower() for item in data["target_keywords"]),
                found_keywords=tuple(str(item).lower() for item in data["found_keywords"]),
                missing_keywords=tuple(str(item).lower() for item in data["missing_keywords"]),
                inventory_path=_resolve_repo_path(str(data["inventory_path"])),
                inputs_dir=_resolve_repo_path(str(data["inputs_dir"])),
                golden_payload_path=_resolve_repo_path(str(data["golden_payload_path"])),
            )
        )
    return tuple(cases)


def _make_job(case: ResumeVerificationCase) -> Job:
    job_id = uuid5(NAMESPACE_URL, f"resume-v2-demo-job:{case.case_id}")
    return Job(
        id=job_id,
        source="manual",
        title=case.job_title,
        raw_title=case.job_title,
        raw_company=case.company_name,
        company_name_raw=case.company_name,
        normalized_company=case.company_name.lower(),
        normalized_title=case.job_title.lower(),
        dedup_hash=f"resume-v2-demo:{case.case_id}",
        description=case.description,
        url=f"https://example.com/{case.case_id}",
        apply_url=f"https://example.com/{case.case_id}",
    )


def _make_analysis(job: Job, case: ResumeVerificationCase) -> JobAnalysis:
    return JobAnalysis(
        job_id=job.id,
        matched_persona=case.persona,
        found_keywords=list(case.found_keywords),
        missing_keywords=list(case.missing_keywords),
        ats_compatibility_score=0.85,
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(f"{canonical_json_dumps(value)}\n", encoding="utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_verification_bundle(
    case: ResumeVerificationCase,
    *,
    output_root: Path,
    playwright_timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Generate one local resume-v2 verification bundle and return its manifest."""
    job = _make_job(case)
    analysis = _make_analysis(job, case)

    evidence_package = build_resume_evidence_package(
        job,
        inventory_path=case.inventory_path,
        inputs_dir=case.inputs_dir,
    )
    planned = plan_resume_artifacts(
        evidence_package,
        persona=case.persona,
        target_keywords=set(case.target_keywords),
        found_keywords=set(case.found_keywords),
        missing_keywords=set(case.missing_keywords),
        template_version=TEMPLATE_VERSION,
        fallback_enabled=False,
    )
    html = render_html(planned.payload, planned.layout_plan)
    pdf_bytes = render_html_to_pdf_bytes(html, timeout_ms=playwright_timeout_ms)
    actual_page_count = count_pdf_pages(pdf_bytes)
    if actual_page_count != 1:
        raise RuntimeError(
            f"Verification case {case.case_id} rendered {actual_page_count} pages; expected 1"
        )

    fit_diagnostics = planned.fit_diagnostics.__class__(
        selected_limits=planned.fit_diagnostics.selected_limits,
        attempted_limit_labels=planned.fit_diagnostics.attempted_limit_labels,
        estimated_total_height_pt=planned.fit_diagnostics.estimated_total_height_pt,
        estimated_page_count=planned.fit_diagnostics.estimated_page_count,
        planner_fit_passed=planned.fit_diagnostics.planner_fit_passed,
        fallback_enabled=planned.fit_diagnostics.fallback_enabled,
        actual_page_count=actual_page_count,
        section_measurements=planned.fit_diagnostics.section_measurements,
        compaction_notes=planned.fit_diagnostics.compaction_notes,
        page_geometry=planned.fit_diagnostics.page_geometry,
        schema_version=planned.fit_diagnostics.schema_version,
    )
    artifact_bundle_id = str(
        uuid5(NAMESPACE_URL, f"resume-v2-demo:{case.case_id}:{planned.payload.compute_hash()}")
    )
    _, payload_document, diagnostics_document = build_resume_sidecar_documents(
        job_id=job.id,
        persona=case.persona,
        generated_at=DEMO_GENERATED_AT,
        artifact_bundle_id=artifact_bundle_id,
        analysis=analysis,
        evidence_package=evidence_package,
        payload=planned.payload,
        fit_result=planned.fit_result,
        layout_plan=planned.layout_plan,
        fit_diagnostics=fit_diagnostics,
        fit_outcome=FIT_OUTCOME_SUCCESS_ONE_PAGE,
    )

    case_output_dir = output_root / case.case_id
    if case_output_dir.exists():
        shutil.rmtree(case_output_dir)
    case_output_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = case_output_dir / "resume.pdf"
    payload_path = case_output_dir / "payload.json"
    diagnostics_path = case_output_dir / "diagnostics.json"
    manifest_path = case_output_dir / "manifest.json"

    pdf_path.write_bytes(pdf_bytes)
    _write_json(payload_path, payload_document)
    _write_json(diagnostics_path, diagnostics_document)

    expected_payload = json.loads(case.golden_payload_path.read_text(encoding="utf-8"))
    payload_matches_golden = planned.payload.to_dict() == expected_payload
    if not payload_matches_golden:
        raise RuntimeError(
            f"Verification case {case.case_id} payload did not match golden fixture "
            f"{case.golden_payload_path.relative_to(REPO_ROOT)}"
        )

    case_manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "case_id": case.case_id,
        "label": case.label,
        "job": {
            "id": str(job.id),
            "title": case.job_title,
            "company_name": case.company_name,
        },
        "fixture_paths": {
            "inventory_path": _display_path(case.inventory_path),
            "inputs_dir": _display_path(case.inputs_dir),
            "golden_payload_path": _display_path(case.golden_payload_path),
        },
        "fit_outcome": FIT_OUTCOME_SUCCESS_ONE_PAGE,
        "actual_page_count": actual_page_count,
        "payload_matches_golden": payload_matches_golden,
        "hashes": {
            "pdf_sha256": _sha256_bytes(pdf_bytes),
            "payload_sha256": _sha256_text(payload_path.read_text(encoding="utf-8")),
            "diagnostics_sha256": _sha256_text(diagnostics_path.read_text(encoding="utf-8")),
            "payload_hash": payload_document["payload_hash"],
            "inputs_hash": payload_document["inputs_hash"],
        },
        "source_summary": diagnostics_document["resume_v2"]["evidence_completeness"],
        "output_files": {
            "pdf": _display_path(pdf_path),
            "payload": _display_path(payload_path),
            "diagnostics": _display_path(diagnostics_path),
        },
        "notes": [
            "Fixture-backed local verification only.",
            "No live provider or auto-apply claim is made by this bundle.",
            "The payload golden comparison verifies deterministic structured output for this case.",
        ],
    }
    case_manifest["output_files"]["manifest"] = _display_path(manifest_path)
    _write_json(manifest_path, case_manifest)
    return case_manifest


def write_verification_bundle(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cases: tuple[ResumeVerificationCase, ...] | None = None,
    commands_summary: str | None = None,
) -> dict[str, Any]:
    """Generate the full resume-v2 demo bundle and return the root manifest."""
    cases_to_run = cases or load_verification_cases()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    case_manifests = [
        build_verification_bundle(case, output_root=output_dir) for case in cases_to_run
    ]

    commands_path: Path | None = None
    if commands_summary:
        commands_path = output_dir / "commands_run.txt"
        commands_path.write_text(commands_summary.rstrip() + "\n", encoding="utf-8")

    root_manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "output_root": _display_path(output_dir),
        "case_count": len(case_manifests),
        "cases": case_manifests,
        "generated_at": DEMO_GENERATED_AT.isoformat(),
        "output_files": {
            "manifest": _display_path(output_dir / "manifest.json"),
        },
        "notes": [
            "This bundle is built from local fixtures, not live providers.",
            "The root directory contains manifest.json and commands_run.txt when command capture is provided.",
            "Each case directory contains resume.pdf, payload.json, diagnostics.json, and manifest.json.",
        ],
    }
    if commands_path is not None:
        root_manifest["output_files"]["commands_run"] = _display_path(commands_path)
    _write_json(output_dir / "manifest.json", root_manifest)
    return root_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Local output directory for the resume-v2 verification bundle.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Optional case id to run. May be passed more than once.",
    )
    args = parser.parse_args()

    requested_case_ids = set(args.case_ids or [])
    loaded_cases = load_verification_cases()
    selected_cases = (
        tuple(case for case in loaded_cases if case.case_id in requested_case_ids)
        if requested_case_ids
        else loaded_cases
    )
    if requested_case_ids and len(selected_cases) != len(requested_case_ids):
        missing = sorted(requested_case_ids - {case.case_id for case in selected_cases})
        raise SystemExit(f"Unknown verification case(s): {', '.join(missing)}")

    output_dir = Path(args.output_dir)
    write_verification_bundle(
        output_dir=output_dir,
        cases=selected_cases,
        commands_summary=os.environ.get("JOBBOT_VERIFY_RESUME_V2_COMMANDS"),
    )
    print(_display_path(output_dir / "manifest.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
