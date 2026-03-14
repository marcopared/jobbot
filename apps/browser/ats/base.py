from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from core.db.models import InterventionReason


@dataclass
class HandlerResult:
    submitted: bool
    intervention_required: bool
    reason: InterventionReason | None = None
    note: str | None = None
    apply_clicked: bool = False
    resume_uploaded: bool = False
    fields_snapshot: dict | None = None
    current_url: str | None = None


class BaseATSHandler(ABC):
    def _run_initial_interaction(
        self,
        page,
        apply_selectors: str,
        resume_path: str | None = None,
        settle_ms: int = 2500,
    ) -> dict:
        """Click Apply, then snapshot currently filled fields."""
        telemetry = {
            "apply_clicked": False,
            "resume_uploaded": False,
            "fields_snapshot": None,
            "current_url": page.url,
        }

        apply_button = page.query_selector(apply_selectors)
        if not apply_button:
            return telemetry

        apply_button.click(timeout=5000)
        page.wait_for_timeout(1200)
        telemetry["apply_clicked"] = True
        telemetry["current_url"] = page.url

        if resume_path:
            uploaded = self._upload_resume(page, resume_path)
            telemetry["resume_uploaded"] = uploaded

        page.wait_for_timeout(settle_ms)
        telemetry["fields_snapshot"] = self._snapshot_filled_fields(page)
        telemetry["current_url"] = page.url
        return telemetry

    def _upload_resume(self, page, resume_path: str) -> bool:
        resume_file = Path(resume_path)
        if not resume_file.exists():
            return False

        for file_input in page.query_selector_all("input[type='file']"):
            input_name = (
                (file_input.get_attribute("name") or "")
                + " "
                + (file_input.get_attribute("id") or "")
                + " "
                + (file_input.get_attribute("accept") or "")
            ).lower()
            if any(token in input_name for token in ("resume", "cv", ".pdf", "application")):
                file_input.set_input_files(str(resume_file))
                return True
        return False

    def _snapshot_filled_fields(self, page) -> dict:
        return page.evaluate(
            """
            () => {
                const fields = Array.from(
                    document.querySelectorAll('input, textarea, select')
                );
                const filled = fields.filter((field) => {
                    if (field.tagName.toLowerCase() === 'select') {
                        return Boolean(field.value);
                    }
                    if (field.type === 'checkbox' || field.type === 'radio') {
                        return field.checked;
                    }
                    return Boolean(field.value && String(field.value).trim());
                });

                const sample = filled.slice(0, 15).map((field) => ({
                    name: field.name || null,
                    id: field.id || null,
                    type: field.type || field.tagName.toLowerCase(),
                    valuePreview: String(field.value || '').slice(0, 80),
                }));

                return {
                    total_fields: fields.length,
                    filled_fields: filled.length,
                    sample,
                };
            }
            """
        )

    @abstractmethod
    def handle(self, page, resume_path: str | None = None, settle_ms: int = 2500) -> HandlerResult:
        """Handle ATS-specific interactions and return outcome."""
        raise NotImplementedError
