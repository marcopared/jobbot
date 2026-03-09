from dataclasses import dataclass

from core.db.models import InterventionReason


@dataclass
class DetectionResult:
    name: str
    reason: InterventionReason


DETECTOR_CHECKS = [
    {
        "name": "recaptcha",
        "reason": InterventionReason.CAPTCHA,
        "selectors": [
            'iframe[src*="recaptcha"]',
            'iframe[title*="reCAPTCHA"]',
            "#recaptcha",
            ".g-recaptcha",
        ],
    },
    {
        "name": "hcaptcha",
        "reason": InterventionReason.CAPTCHA,
        "selectors": ['iframe[src*="hcaptcha"]', ".h-captcha"],
    },
    {
        "name": "cloudflare",
        "reason": InterventionReason.BLOCKED,
        "selectors": [
            "#challenge-running",
            "#challenge-stage",
            'iframe[src*="challenges.cloudflare.com"]',
        ],
        "text_patterns": [
            "checking your browser",
            "verify you are human",
            "just a moment",
        ],
    },
    {
        "name": "login_wall",
        "reason": InterventionReason.LOGIN_REQUIRED,
        "text_patterns": [
            "sign in to continue",
            "log in to apply",
            "create an account",
        ],
    },
]


def detect_blocks(page) -> DetectionResult | None:
    """Check page for CAPTCHA/MFA/block indicators."""
    body_text = (page.text_content("body") or "").lower()

    for check in DETECTOR_CHECKS:
        for selector in check.get("selectors", []):
            if page.query_selector(selector):
                return DetectionResult(name=check["name"], reason=check["reason"])
        for pattern in check.get("text_patterns", []):
            if pattern.lower() in body_text:
                return DetectionResult(name=check["name"], reason=check["reason"])
    return None
