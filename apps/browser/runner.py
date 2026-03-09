import logging
import traceback
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import json
from pathlib import Path
from uuid import UUID

from playwright.sync_api import sync_playwright

from apps.api.settings import Settings
from apps.browser.ats import get_handler
from apps.browser.detectors import detect_blocks
from apps.worker.tasks.notify import send_notification
from core.db.models import (
    Application,
    ApplicationStatus,
    ApplyMethod,
    Artifact,
    ArtifactKind,
    ATSType,
    Intervention,
    InterventionStatus,
    Job,
    JobStatus,
)
from core.resumes.manager import prepare_resume
from core.scraping.base import detect_ats_type

logger = logging.getLogger(__name__)
settings = Settings()


def _write_log_artifact(
    session,
    job_id: UUID,
    application_id: UUID,
    label: str,
    payload: dict,
) -> Artifact:
    artifact_root = Path(settings.artifact_dir)
    job_dir = artifact_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_name = f"{label}_{timestamp}.log"
    log_path = job_dir / log_name
    log_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    artifact = Artifact(
        job_id=job_id,
        application_id=application_id,
        kind=ArtifactKind.LOG.value,
        filename=log_name,
        path=str(log_path.relative_to(artifact_root)),
        size_bytes=log_path.stat().st_size,
        meta_json={"label": label},
    )
    session.add(artifact)
    session.flush()
    return artifact


def _record_milestone(
    session,
    job_id: UUID,
    application_id: UUID,
    label: str,
    page=None,
    details: dict | None = None,
) -> None:
    payload = {
        "label": label,
        "timestamp": datetime.now(UTC).isoformat(),
        "url": page.url if page else None,
        "details": details or {},
    }
    _write_log_artifact(
        session=session,
        job_id=job_id,
        application_id=application_id,
        label=label,
        payload=payload,
    )
    if page is not None:
        _capture_artifacts(session=session, page=page, job_id=job_id, application_id=application_id)


def get_extension_id(context) -> str:
    sw = (
        context.service_workers[0]
        if context.service_workers
        else context.wait_for_event("serviceworker", timeout=5000)
    )
    return sw.url.split("/")[2]


def _profile_base_dir() -> Path:
    if settings.simplify_enabled:
        _, profile_dir = _required_simplify_paths()
        return profile_dir
    return (Path(settings.profile_dir) / settings.playwright_profile_name).resolve()


def _required_simplify_paths() -> tuple[Path, Path]:
    extension_path = (settings.simplify_extension_path or "").strip()
    profile_path = (settings.simplify_profile_dir or "").strip()
    if not extension_path:
        raise RuntimeError("Missing required env var: SIMPLIFY_EXTENSION_PATH")
    if not profile_path:
        raise RuntimeError("Missing required env var: SIMPLIFY_PROFILE_DIR")
    return Path(extension_path).resolve(), Path(profile_path).resolve()


@contextmanager
def _acquire_profile_lock(profile_dir: Path):
    profile_dir.mkdir(parents=True, exist_ok=True)
    lock_path = profile_dir / ".profile.lock"
    lock_handle = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise RuntimeError("profile_in_use: another apply run is using this browser profile") from exc

    try:
        lock_handle.write(str(datetime.now(UTC).isoformat()))
        lock_handle.flush()
        yield
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def _launch_browser_context(playwright):
    if settings.simplify_enabled:
        ext_path, profile_dir = _required_simplify_paths()
        logger.info(
            "Launching Playwright in Simplify mode with extension_path=%s profile_dir=%s",
            ext_path,
            profile_dir,
        )
        profile_dir.mkdir(parents=True, exist_ok=True)
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chromium",
            headless=not settings.playwright_headful,
            slow_mo=settings.playwright_slow_mo_ms,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
            ],
        )

    profile_path = (Path(settings.profile_dir) / settings.playwright_profile_name).resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        headless=not settings.playwright_headful,
        slow_mo=settings.playwright_slow_mo_ms,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )


def _capture_artifacts(session, page, job_id: UUID, application_id: UUID) -> tuple[Artifact, Artifact]:
    artifact_root = Path(settings.artifact_dir)
    job_dir = artifact_root / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    screenshot_name = f"screenshot_{timestamp}.png"
    screenshot_path = job_dir / screenshot_name
    page.screenshot(path=str(screenshot_path), full_page=True)

    html_name = f"page_{timestamp}.html"
    html_path = job_dir / html_name
    html_path.write_text(page.content(), encoding="utf-8")

    screenshot_artifact = Artifact(
        job_id=job_id,
        application_id=application_id,
        kind=ArtifactKind.SCREENSHOT.value,
        filename=screenshot_name,
        path=str(screenshot_path.relative_to(artifact_root)),
        size_bytes=screenshot_path.stat().st_size,
    )
    html_artifact = Artifact(
        job_id=job_id,
        application_id=application_id,
        kind=ArtifactKind.HTML.value,
        filename=html_name,
        path=str(html_path.relative_to(artifact_root)),
        size_bytes=html_path.stat().st_size,
    )
    session.add(screenshot_artifact)
    session.add(html_artifact)
    session.flush()
    return screenshot_artifact, html_artifact


def _create_intervention(
    session,
    job: Job,
    application: Application,
    reason: str,
    last_url: str | None,
    screenshot_artifact_id: UUID | None,
    html_artifact_id: UUID | None,
) -> Intervention:
    intervention = Intervention(
        job_id=job.id,
        application_id=application.id,
        status=InterventionStatus.OPEN.value,
        reason=reason,
        last_url=last_url,
        screenshot_artifact_id=screenshot_artifact_id,
        html_artifact_id=html_artifact_id,
    )
    session.add(intervention)
    session.flush()
    return intervention


def _notify(title: str, message: str, url: str | None = None) -> None:
    try:
        send_notification.delay(title=title, message=message, url=url)
    except Exception:
        logger.warning("Failed to enqueue notification: %s", title)


def _resolve_target_url(job: Job) -> str:
    """Prefer direct apply URL (JobSpy job_url_direct) over listing URL."""
    if job.apply_url and str(job.apply_url).strip():
        return str(job.apply_url).strip()

    payload = job.source_payload_json if isinstance(job.source_payload_json, dict) else {}
    direct_from_payload = payload.get("job_url_direct")
    if isinstance(direct_from_payload, str) and direct_from_payload.strip():
        # Backfill in-memory so this run can still use direct apply URL.
        job.apply_url = direct_from_payload.strip()
        return job.apply_url

    return job.url


def apply_job(session, job_id: str) -> dict:
    """Playwright apply runner with Simplify persistent profile.

    MVP path: relies on Simplify account state (login/profile/resume already set
    in Simplify). Jobbot-driven local resume replacement is deferred.
    """
    job_uuid = UUID(job_id)
    job = session.get(Job, job_uuid)
    if not job:
        return {"job_id": job_id, "error": "job_not_found"}

    application = Application(
        job_id=job_uuid,
        status=ApplicationStatus.STARTED.value,
        method=ApplyMethod.PLAYWRIGHT.value,
    )
    session.add(application)
    session.flush()

    # Retained for compatibility/prep work. Current Simplify-first MVP does not
    # depend on Jobbot replacing the resume inside Simplify during apply runs.
    resume_artifact = prepare_resume(session=session, job_id=job_uuid)
    resume_path: str | None = None
    if resume_artifact is not None:
        resume_path = str(Path(settings.artifact_dir) / resume_artifact.path)

    target_url = _resolve_target_url(job)
    page = None

    try:
        with sync_playwright() as p:
            profile_base_dir = _profile_base_dir()
            with _acquire_profile_lock(profile_base_dir):
                context = _launch_browser_context(p)
                try:
                    _record_milestone(
                        session=session,
                        job_id=job.id,
                        application_id=application.id,
                        label="browser_launched",
                        details={
                            "profile_dir": str(profile_base_dir),
                            "simplify_enabled": settings.simplify_enabled,
                        },
                    )
                    if settings.simplify_enabled:
                        extension_id = get_extension_id(context)
                        logger.info("Simplify loaded: %s", extension_id)
                        print("Simplify loaded:", extension_id)
                        _record_milestone(
                            session=session,
                            job_id=job.id,
                            application_id=application.id,
                            label="extension_detected",
                            details={
                                "extension_id": extension_id,
                                "extension_path": settings.simplify_extension_path,
                            },
                        )

                    page = context.new_page()
                    page.set_default_timeout(settings.playwright_timeout_ms)
                    page.goto(target_url, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle")
                    _record_milestone(
                        session=session,
                        job_id=job.id,
                        application_id=application.id,
                        label="job_page_opened",
                        page=page,
                        details={"target_url": target_url},
                    )

                    blocked = detect_blocks(page)
                    if blocked:
                        _record_milestone(
                            session=session,
                            job_id=job.id,
                            application_id=application.id,
                            label="submission_page_reached_or_blocked",
                            page=page,
                            details={"blocked_reason": blocked.reason.value},
                        )
                        screenshot_artifact, html_artifact = _capture_artifacts(
                            session, page, job.id, application.id
                        )
                        intervention = _create_intervention(
                            session=session,
                            job=job,
                            application=application,
                            reason=blocked.reason.value,
                            last_url=page.url,
                            screenshot_artifact_id=screenshot_artifact.id,
                            html_artifact_id=html_artifact.id,
                        )
                        application.status = ApplicationStatus.INTERVENTION_REQUIRED.value
                        job.status = JobStatus.INTERVENTION_REQUIRED.value
                        _notify(
                            title="Intervention Needed",
                            message=f"{job.title} at {job.company_name_raw} - {blocked.reason.value}",
                            url=f"{settings.ui_base_url}/interventions/{intervention.id}",
                        )
                        return {
                            "job_id": job_id,
                            "application_id": str(application.id),
                            "status": application.status,
                            "reason": blocked.reason.value,
                        }

                    final_url = page.url or target_url
                    ats_type = detect_ats_type(final_url)
                    if not isinstance(ats_type, ATSType):
                        ats_type = ATSType.UNKNOWN
                    job.ats_type = ats_type.value

                    handler = get_handler(ats_type)
                    handler_result = handler.handle(
                        page,
                        resume_path=resume_path,
                        settle_ms=max(settings.playwright_slow_mo_ms * 4, 2500),
                    )
                    _record_milestone(
                        session=session,
                        job_id=job.id,
                        application_id=application.id,
                        label="apply_button_clicked",
                        page=page,
                        details={"clicked": handler_result.apply_clicked, "ats_type": job.ats_type},
                    )
                    _record_milestone(
                        session=session,
                        job_id=job.id,
                        application_id=application.id,
                        label="resume_field_interaction",
                        page=page,
                        details={
                            "uploaded": handler_result.resume_uploaded,
                            "resume_artifact_id": str(resume_artifact.id) if resume_artifact else None,
                            "mvp_data_source": "simplify_account_state",
                            "local_resume_replacement_deferred": True,
                        },
                    )
                    _record_milestone(
                        session=session,
                        job_id=job.id,
                        application_id=application.id,
                        label="autofill_completed",
                        page=page,
                        details={
                            "fields_snapshot": handler_result.fields_snapshot,
                            "handler_note": handler_result.note,
                        },
                    )

                    post_interaction_block = detect_blocks(page)
                    if post_interaction_block:
                        _record_milestone(
                            session=session,
                            job_id=job.id,
                            application_id=application.id,
                            label="submission_page_reached_or_blocked",
                            page=page,
                            details={"blocked_reason": post_interaction_block.reason.value},
                        )
                        screenshot_artifact, html_artifact = _capture_artifacts(
                            session, page, job.id, application.id
                        )
                        intervention = _create_intervention(
                            session=session,
                            job=job,
                            application=application,
                            reason=post_interaction_block.reason.value,
                            last_url=page.url,
                            screenshot_artifact_id=screenshot_artifact.id,
                            html_artifact_id=html_artifact.id,
                        )
                        application.status = ApplicationStatus.INTERVENTION_REQUIRED.value
                        job.status = JobStatus.INTERVENTION_REQUIRED.value
                        _notify(
                            title="Intervention Needed",
                            message=f"{job.title} at {job.company_name_raw} - {post_interaction_block.reason.value}",
                            url=f"{settings.ui_base_url}/interventions/{intervention.id}",
                        )
                        return {
                            "job_id": job_id,
                            "application_id": str(application.id),
                            "status": application.status,
                            "reason": post_interaction_block.reason.value,
                        }

                    if handler_result.intervention_required:
                        _record_milestone(
                            session=session,
                            job_id=job.id,
                            application_id=application.id,
                            label="submission_page_reached_or_blocked",
                            page=page,
                            details={
                                "blocked_reason": (
                                    handler_result.reason.value
                                    if handler_result.reason
                                    else "unexpected_field"
                                )
                            },
                        )
                        screenshot_artifact, html_artifact = _capture_artifacts(
                            session, page, job.id, application.id
                        )
                        intervention = _create_intervention(
                            session=session,
                            job=job,
                            application=application,
                            reason=(
                                handler_result.reason.value
                                if handler_result.reason is not None
                                else "unexpected_field"
                            ),
                            last_url=handler_result.current_url or final_url,
                            screenshot_artifact_id=screenshot_artifact.id,
                            html_artifact_id=html_artifact.id,
                        )
                        application.status = ApplicationStatus.INTERVENTION_REQUIRED.value
                        job.status = JobStatus.INTERVENTION_REQUIRED.value
                        application.fields_json = handler_result.fields_snapshot
                        _notify(
                            title="Intervention Needed",
                            message=f"{job.title} at {job.company_name_raw} - unexpected_field",
                            url=f"{settings.ui_base_url}/interventions/{intervention.id}",
                        )
                        return {
                            "job_id": job_id,
                            "application_id": str(application.id),
                            "status": application.status,
                            "ats_type": job.ats_type,
                            "fields_snapshot": handler_result.fields_snapshot,
                        }

                    if handler_result.submitted:
                        _record_milestone(
                            session=session,
                            job_id=job.id,
                            application_id=application.id,
                            label="submission_page_reached_or_blocked",
                            page=page,
                            details={"blocked_reason": None, "submitted": True},
                        )
                        application.status = ApplicationStatus.SUBMITTED.value
                        job.status = JobStatus.APPLIED.value
                        application.fields_json = handler_result.fields_snapshot
                        _notify(
                            title="Applied Successfully",
                            message=f"{job.title} at {job.company_name_raw}",
                            url=f"{settings.ui_base_url}/jobs/{job.id}",
                        )
                        return {
                            "job_id": job_id,
                            "application_id": str(application.id),
                            "status": application.status,
                            "ats_type": job.ats_type,
                        }

                    _record_milestone(
                        session=session,
                        job_id=job.id,
                        application_id=application.id,
                        label="submission_page_reached_or_blocked",
                        page=page,
                        details={"blocked_reason": "none", "submitted": False},
                    )
                    application.status = ApplicationStatus.FAILED.value
                    application.error_text = "ATS handler returned no actionable result."
                    job.status = JobStatus.APPLY_FAILED.value
                    _notify(
                        title="Apply Failed",
                        message=f"{job.title} - {application.error_text}",
                        url=f"{settings.ui_base_url}/jobs/{job.id}",
                    )
                    return {
                        "job_id": job_id,
                        "application_id": str(application.id),
                        "status": application.status,
                        "error": application.error_text,
                    }
                finally:
                    context.close()
    except Exception as exc:
        logger.exception("apply_job runner failed for job_id=%s", job_id)
        application.status = ApplicationStatus.FAILED.value
        application.error_text = str(exc)
        job.status = JobStatus.APPLY_FAILED.value

        if page:
            try:
                _capture_artifacts(session, page, job.id, application.id)
            except Exception:
                logger.exception("Failed to capture failure artifacts for job_id=%s", job_id)

        artifact_root = Path(settings.artifact_dir)
        job_dir = artifact_root / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_name = f"error_{timestamp}.log"
        log_path = job_dir / log_name
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        session.add(
            Artifact(
                job_id=job.id,
                application_id=application.id,
                kind=ArtifactKind.LOG.value,
                filename=log_name,
                path=str(log_path.relative_to(artifact_root)),
                size_bytes=log_path.stat().st_size,
                meta_json={"error": str(exc)},
            )
        )
        _notify(
            title="Apply Failed",
            message=f"{job.title} - {str(exc)[:100]}",
            url=f"{settings.ui_base_url}/jobs/{job.id}",
        )
        return {
            "job_id": job_id,
            "application_id": str(application.id),
            "status": application.status,
            "error": str(exc),
        }
