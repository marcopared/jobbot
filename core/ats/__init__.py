"""Deterministic ATS keyword extraction (EPIC 5).

No LLM. Extracts keywords from job descriptions, maps synonyms, compares to user skills.
"""

from core.ats.extraction import extract_ats_signals

__all__ = ["extract_ats_signals"]
