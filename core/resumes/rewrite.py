"""Conservative rewrite rules for resume bullets (EPIC 7).

v1: No generative rewrite. Only selection; bullets used as-is from inventory.
Future: light rephrasing to front-load ATS keywords while keeping facts intact.
"""


def apply_conservative_rewrite(
    bullet_text: str,
    missing_keywords: set[str],
) -> str:
    """
    Apply conservative rewrite to a bullet. v1 returns text unchanged.

    Constraints: never invent metrics or experience; only reorder/phrase when
    the fact is already present.
    """
    return bullet_text
