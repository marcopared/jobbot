import logging
import re

from core.resumes.keywords import normalize_keyword, extract_keywords

logger = logging.getLogger(__name__)

_SECTION_HEADERS = re.compile(
    r"^(skills|technical skills|experience|work experience|education|summary|objective|projects)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split resume text into (header, body) sections."""
    positions = [(m.start(), m.group().strip()) for m in _SECTION_HEADERS.finditer(text)]
    if not positions:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    if positions[0][0] > 0:
        sections.append(("", text[: positions[0][0]]))
    for i, (pos, header) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = text[pos + len(header) : end].strip()
        sections.append((header, body))
    return sections


def _reorder_skills_section(body: str, jd_keywords: set[str], addable: set[str]) -> str:
    """Reorder skills to front-load JD matches; append addable skills."""
    items = [s.strip() for s in re.split(r"[,\n•\-|]", body) if s.strip()]
    matched = [s for s in items if normalize_keyword(s) in jd_keywords]
    rest = [s for s in items if s not in matched]
    to_add = sorted(addable - {normalize_keyword(s) for s in items})
    combined = matched + rest + to_add
    return ", ".join(combined)


def _reorder_experience_bullets(body: str, jd_keywords: set[str]) -> str:
    """Reorder bullets within each role to prioritize JD-keyword-containing lines."""
    lines = body.split("\n")
    result: list[str] = []
    bullet_block: list[str] = []

    def flush_bullets() -> None:
        if not bullet_block:
            return
        with_kw = [b for b in bullet_block if extract_keywords(b) & jd_keywords]
        without_kw = [b for b in bullet_block if b not in with_kw]
        result.extend(with_kw + without_kw)
        bullet_block.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "• ", "* ")):
            bullet_block.append(line)
        else:
            flush_bullets()
            result.append(line)
    flush_bullets()
    return "\n".join(result)


def _inject_summary_keywords(body: str, missing_keywords: set[str], limit: int = 3) -> str:
    """Inject top N missing JD keywords into summary if not already present."""
    body_lower = body.lower()
    to_inject = [kw for kw in sorted(missing_keywords) if kw not in body_lower][:limit]
    if not to_inject:
        return body
    injection = "Additional expertise: " + ", ".join(to_inject) + "."
    return body.rstrip() + "\n" + injection


def tailor_resume(
    resume_text: str,
    ats_breakdown: dict,
    master_skills: list[str],
    job_description: str,
) -> str:
    """
    Produce tailored resume text with improved ATS alignment.
    V1 strategy (rule-based):
      1. Parse resume into sections.
      2. Skills section: reorder to front-load JD-matching skills; append
         missing skills the operator actually has (from master_skills).
      3. Experience bullets: reorder within each role to prioritize bullets
         containing JD keywords.
      4. Summary line: inject top 3 missing JD keywords if not already present.
      5. Return modified text.
    Falls back to original resume_text on any error.
    """
    try:
        missing = set(ats_breakdown.get("skills_missing", []))
        jd_kw = extract_keywords(job_description)
        addable = missing & {normalize_keyword(s) for s in master_skills}

        sections = _split_sections(resume_text)
        rebuilt: list[str] = []

        for header, body in sections:
            header_lower = header.lower()
            if "skill" in header_lower:
                body = _reorder_skills_section(body, jd_kw, addable)
            elif "experience" in header_lower:
                body = _reorder_experience_bullets(body, jd_kw)
            elif "summary" in header_lower or "objective" in header_lower:
                body = _inject_summary_keywords(body, missing)

            if header:
                rebuilt.append(f"{header}\n{body}")
            else:
                rebuilt.append(body)

        return "\n\n".join(rebuilt)
    except Exception:
        logger.warning("Tailoring failed, returning original resume text")
        return resume_text
