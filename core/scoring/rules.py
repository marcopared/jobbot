"""Scoring rules config (SPEC §10, EPIC 5).

Deterministic weighted heuristic. Five factors, each 0-100, combined with weights.
Tuning knobs: SCORING_WEIGHTS, keyword lists below.
"""

# Factor weights (must sum to 1.0)
SCORING_WEIGHTS = {
    "title_relevance": 0.25,    # 25%
    "seniority_fit": 0.20,      # 20%
    "domain_alignment": 0.20,   # 20%
    "location_remote": 0.20,    # 20%
    "tech_stack": 0.15,         # 15%
}

# Target job titles: matches score high (title relevance)
TARGET_TITLES = [
    "software engineer",
    "backend engineer",
    "backend developer",
    "platform engineer",
    "infrastructure engineer",
    "full stack",
    "fullstack",
    "senior software engineer",
    "senior backend",
]

# Negative title signals (junior, over-senior)
JUNIOR_SIGNALS = ["intern", "junior", "entry", "associate", "graduate"]
OVER_SENIOR_SIGNALS = ["staff", "principal", "architect", "director", "vp", "head of"]

# Domain keywords (industry/vertical alignment)
DOMAIN_KEYWORDS = {
    "fintech": 100,
    "financial": 80,
    "payments": 85,
    "banking": 75,
    "crypto": 70,
    "blockchain": 65,
    "trading": 75,
    "startup": 60,
    "series a": 70,
    "series b": 65,
    "seed": 55,
    "infrastructure": 80,
    "platform": 80,
    "developer tools": 75,
}

# Location/remote signals
LOCATION_SIGNALS = {
    "remote": 100,
    "distributed": 90,
    "anywhere": 90,
    "hybrid": 75,
    "new york": 70,
    "nyc": 70,
    "sf": 60,
    "san francisco": 60,
}
