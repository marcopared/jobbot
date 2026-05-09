from core.resumes.keywords import extract_keywords


def compute_ats_match(resume_text: str, job_description: str) -> tuple[float, dict]:
    """
    Compare resume keywords against job description keywords.
    Returns (score 0-100, breakdown dict).
    """
    resume_kw = extract_keywords(resume_text)
    jd_kw = extract_keywords(job_description)

    if not jd_kw:
        return 0.0, {"error": "no_keywords_found_in_jd"}

    matched = resume_kw & jd_kw
    missing = jd_kw - resume_kw
    overlap_pct = len(matched) / len(jd_kw) * 100

    breakdown = {
        "keyword_overlap_pct": round(overlap_pct, 1),
        "skills_found": sorted(matched),
        "skills_missing": sorted(missing),
        "resume_extra_skills": sorted(resume_kw - jd_kw),
        "total_jd_keywords": len(jd_kw),
        "matched_keywords": len(matched),
        "suggestions": [f"Add '{kw}' to resume" for kw in sorted(missing)[:5]],
    }

    return round(overlap_pct, 1), breakdown
