"""PDF rendering via Playwright (EPIC 7). v1 always headless."""

import logging
from io import BytesIO

from core.resumes.layout_types import DEFAULT_PAGE_GEOMETRY

logger = logging.getLogger(__name__)

_PDF_OPTS = {
    "format": DEFAULT_PAGE_GEOMETRY.page_size,
    "margin": DEFAULT_PAGE_GEOMETRY.playwright_margin(),
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


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Count PDF pages from rendered bytes for fit validation."""
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError("pdfplumber not installed; cannot validate rendered PDF pages") from e

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        return len(pdf.pages)
