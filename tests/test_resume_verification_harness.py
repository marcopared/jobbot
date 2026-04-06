"""Tests for the fixture-backed resume-v2 verification harness."""

from __future__ import annotations

import json

from core.resumes.verification_harness import load_verification_cases, write_verification_bundle


def test_verification_harness_writes_expected_case_bundles(monkeypatch, tmp_path):
    import core.resumes.verification_harness as harness

    monkeypatch.setattr(harness, "render_html_to_pdf_bytes", lambda html, timeout_ms: b"%PDF-1.4")
    monkeypatch.setattr(harness, "count_pdf_pages", lambda pdf_bytes: 1)

    manifest = write_verification_bundle(
        output_dir=tmp_path / "resume_v2_demo",
        cases=load_verification_cases(),
        commands_summary="bash scripts/verify_resume_v2.sh storage/verification/resume_v2_demo",
    )

    root_dir = tmp_path / "resume_v2_demo"
    assert manifest["case_count"] == 2
    assert manifest["output_files"]["manifest"] == str(root_dir / "manifest.json")
    assert manifest["output_files"]["commands_run"] == str(root_dir / "commands_run.txt")
    assert (root_dir / "commands_run.txt").is_file()
    for case in manifest["cases"]:
        case_dir = root_dir / case["case_id"]
        assert (case_dir / "resume.pdf").is_file()
        assert (case_dir / "payload.json").is_file()
        assert (case_dir / "diagnostics.json").is_file()
        case_manifest = json.loads((case_dir / "manifest.json").read_text())
        assert case_manifest["output_files"]["pdf"] == str(case_dir / "resume.pdf")
        assert case_manifest["output_files"]["payload"] == str(case_dir / "payload.json")
        assert case_manifest["output_files"]["diagnostics"] == str(case_dir / "diagnostics.json")
        assert case_manifest["output_files"]["manifest"] == str(case_dir / "manifest.json")
        assert case_manifest["payload_matches_golden"] is True
        assert case_manifest["fit_outcome"] == "fit_success_one_page"
