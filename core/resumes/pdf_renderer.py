"""PDF rendering via Playwright (EPIC 7)."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PDF_OPTS = {
    "format": "Letter",
    "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    "print_background": True,
}


def render_html_to_pdf_bytes(html_content: str) -> bytes:
    """
    Render HTML to PDF using Playwright. Returns PDF bytes.

    Invoked from Python. Requires: pip install playwright && playwright install chromium
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
            page.set_content(html_content, wait_until="networkidle")
            # Omit path to get bytes instead of writing to file
            pdf_bytes = page.pdf(**_PDF_OPTS)
        finally:
            browser.close()

    if pdf_bytes is None:
        raise RuntimeError("Playwright page.pdf() returned None")
    logger.debug("Rendered PDF: %d bytes", len(pdf_bytes))
    return pdf_bytes


def render_html_to_pdf(html_content: str, output_path: str | Path) -> None:
    """Render HTML to PDF and write to file. For legacy/copy use."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = render_html_to_pdf_bytes(html_content)
    output_path.write_bytes(pdf_bytes)
    logger.info("Rendered PDF to %s", output_path)
