"""PDF rendering via Playwright (EPIC 7). v1 always headless."""

import logging

logger = logging.getLogger(__name__)

_PDF_OPTS = {
    "format": "Letter",
    "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    "print_background": True,
}


def render_html_to_pdf_bytes(html_content: str, *, timeout_ms: int = 30000) -> bytes:
    """
    Render HTML to PDF using Playwright. Returns PDF bytes.

    Invoked from Python. Requires: pip install playwright && playwright install chromium
    v1 always runs headless. timeout_ms applies to content loading (set_content).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        ) from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle", timeout=timeout_ms)
            # Omit path to get bytes instead of writing to file
            pdf_bytes = page.pdf(**_PDF_OPTS)
        finally:
            browser.close()

    if pdf_bytes is None:
        raise RuntimeError("Playwright page.pdf() returned None")
    logger.debug("Rendered PDF: %d bytes", len(pdf_bytes))
    return pdf_bytes
