"""Rules-based persona classifier (EPIC 6 v1).

Deterministic, no LLM. Uses title signals and description keywords.
Fallback: HYBRID when signals are mixed.
"""

from core.classification.interface import PersonaClassifier
from core.matching import keyword_in_text, score_keywords_in_text
from core.classification.rules import (
    BACKEND_KEYWORDS,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MED,
    PLATFORM_INFRA_KEYWORDS,
    TITLE_SIGNALS,
)
from core.classification.types import ClassificationInput, ClassificationResult, Persona


class RulesBasedClassifier(PersonaClassifier):
    """v1 provider: explicit heuristics and weights. Deterministic."""

    def classify(self, inputs: ClassificationInput) -> ClassificationResult:
        combined = _combine_inputs(inputs)
        title_lower = (inputs.normalized_title or "").lower()
        desc_lower = (inputs.description or "").lower()

        # Title-based scores (strong signal) — use word-boundary matching
        backend_title_score = sum(
            1 for s in TITLE_SIGNALS["backend"] if keyword_in_text(title_lower, s)
        )
        platform_title_score = sum(
            1 for s in TITLE_SIGNALS["platform_infra"] if keyword_in_text(title_lower, s)
        )
        hybrid_title_score = sum(
            1 for s in TITLE_SIGNALS["hybrid"] if keyword_in_text(title_lower, s)
        )

        # Description/keyword scores
        backend_desc_score = _score_keywords(combined, BACKEND_KEYWORDS)
        platform_desc_score = _score_keywords(combined, PLATFORM_INFRA_KEYWORDS)

        # ATS categories contribution (if available)
        if inputs.ats_categories:
            backend_desc_score += _score_ats_categories(
                inputs.ats_categories, backend=True
            )
            platform_desc_score += _score_ats_categories(
                inputs.ats_categories, backend=False
            )

        # Combine title (weighted higher) and description
        title_weight = 2.0
        backend_total = backend_title_score * title_weight + backend_desc_score
        platform_total = platform_title_score * title_weight + platform_desc_score

        matched_signals = {
            "backend_title_matches": backend_title_score,
            "platform_title_matches": platform_title_score,
            "hybrid_title_matches": hybrid_title_score,
            "backend_desc_score": round(backend_desc_score, 2),
            "platform_desc_score": round(platform_desc_score, 2),
            "backend_total": round(backend_total, 2),
            "platform_total": round(platform_total, 2),
        }

        # Decision logic with fallbacks
        if hybrid_title_score > 0 and (backend_total > 0 or platform_total > 0):
            return ClassificationResult(
                persona=Persona.HYBRID,
                confidence=CONFIDENCE_MED,
                rationale=_format_rationale(
                    Persona.HYBRID, "hybrid title + mixed signals"
                ),
                matched_signals=matched_signals,
            )

        # Mixed signals: both backend and platform substantial, gap small -> HYBRID
        if backend_total >= 2 and platform_total >= 2 and abs(backend_total - platform_total) < 3:
            return ClassificationResult(
                persona=Persona.HYBRID,
                confidence=CONFIDENCE_MED,
                rationale=_format_rationale(
                    Persona.HYBRID, "mixed backend and platform signals; defaulting to hybrid"
                ),
                matched_signals=matched_signals,
            )

        if backend_total > platform_total:
            if platform_total > 0:
                confidence = CONFIDENCE_MED if backend_total - platform_total < 3 else CONFIDENCE_HIGH
                rationale = "backend-leaning; some platform signals"
            else:
                confidence = CONFIDENCE_HIGH if backend_total >= 2 else CONFIDENCE_MED
                rationale = "clear backend signals"
            return ClassificationResult(
                persona=Persona.BACKEND,
                confidence=confidence,
                rationale=_format_rationale(Persona.BACKEND, rationale),
                matched_signals=matched_signals,
            )

        if platform_total > backend_total:
            if backend_total > 0:
                confidence = CONFIDENCE_MED if platform_total - backend_total < 3 else CONFIDENCE_HIGH
                rationale = "platform-leaning; some backend signals"
            else:
                confidence = CONFIDENCE_HIGH if platform_total >= 2 else CONFIDENCE_MED
                rationale = "clear platform/infra signals"
            return ClassificationResult(
                persona=Persona.PLATFORM_INFRA,
                confidence=confidence,
                rationale=_format_rationale(Persona.PLATFORM_INFRA, rationale),
                matched_signals=matched_signals,
            )

        # Tie or no signals: fallback to HYBRID
        return ClassificationResult(
            persona=Persona.HYBRID,
            confidence=CONFIDENCE_LOW,
            rationale=_format_rationale(
                Persona.HYBRID, "ambiguous/mixed; defaulting to hybrid"
            ),
            matched_signals=matched_signals,
        )


def _combine_inputs(inputs: ClassificationInput) -> str:
    parts = [inputs.normalized_title or "", inputs.description or ""]
    if inputs.found_keywords:
        parts.append(" ".join(inputs.found_keywords))
    return " ".join(parts).lower()


def _score_keywords(text: str, kw_weights: dict) -> float:
    return score_keywords_in_text(text, kw_weights)


def _score_ats_categories(
    categories: dict[str, list[str]], backend: bool
) -> float:
    backend_cats = {"languages", "frameworks", "databases"}
    platform_cats = {"cloud", "tools"}
    score = 0.0
    for cat, kws in categories.items():
        cat_lower = cat.lower()
        if backend and cat_lower in backend_cats:
            score += 0.5 * len(kws)
        elif not backend and cat_lower in platform_cats:
            score += 0.5 * len(kws)
    return score


def _format_rationale(persona: Persona, reason: str) -> str:
    return f"Persona={persona.value} | {reason}"
