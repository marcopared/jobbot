from apps.browser.ats.base import BaseATSHandler, HandlerResult
from core.db.models import InterventionReason


class LeverHandler(BaseATSHandler):
    def handle(self, page, resume_path: str | None = None, settle_ms: int = 2500) -> HandlerResult:
        selectors = (
            "a:has-text('Apply'), button:has-text('Apply'), button:has-text('Apply for this job')"
        )
        telemetry = self._run_initial_interaction(
            page=page,
            apply_selectors=selectors,
            resume_path=resume_path,
            settle_ms=settle_ms,
        )
        if telemetry["apply_clicked"]:
            return HandlerResult(
                submitted=False,
                intervention_required=True,
                reason=InterventionReason.UNEXPECTED_FIELD,
                note=(
                    "Lever apply flow started; manual review required for "
                    "Simplify account-state autofill (local resume replacement deferred)."
                ),
                apply_clicked=True,
                resume_uploaded=bool(telemetry["resume_uploaded"]),
                fields_snapshot=telemetry["fields_snapshot"],
                current_url=telemetry["current_url"],
            )
        return HandlerResult(
            submitted=False,
            intervention_required=True,
            reason=InterventionReason.UNEXPECTED_FIELD,
            note="Lever page loaded but apply button not found.",
            apply_clicked=False,
            resume_uploaded=False,
            fields_snapshot=telemetry["fields_snapshot"],
            current_url=telemetry["current_url"],
        )
