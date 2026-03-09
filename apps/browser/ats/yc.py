from apps.browser.ats.base import BaseATSHandler, HandlerResult
from core.db.models import InterventionReason


class YCHandler(BaseATSHandler):
    def handle(self, page, resume_path: str | None = None, settle_ms: int = 2500) -> HandlerResult:
        return HandlerResult(
            submitted=False,
            intervention_required=True,
            reason=InterventionReason.UNEXPECTED_FIELD,
            note="YC handler is stubbed in V1.",
        )
