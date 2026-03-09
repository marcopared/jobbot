"""Scoring rules config (SPEC §10.1)."""

SCORING_RULES = {
    "title_keywords": {
        "positive": {
            "backend": 2.0,
            "software engineer": 2.0,
            "platform": 1.5,
            "fullstack": 1.0,
            "full stack": 1.0,
            "python": 1.5,
            "api": 1.0,
        },
        "negative": {
            "staff": -2.0,
            "principal": -3.0,
            "director": -3.0,
            "vp": -3.0,
            "intern": -5.0,
            "junior": -1.0,
        },
    },
    "description_keywords": {
        "fintech": 2.0,
        "financial": 1.5,
        "payments": 1.5,
        "banking": 1.0,
        "crypto": 1.0,
        "blockchain": 0.5,
        "trading": 1.0,
        "python": 1.0,
        "fastapi": 1.5,
        "django": 0.5,
        "aws": 0.5,
        "startup": 1.0,
        "series a": 1.5,
        "series b": 1.0,
        "seed": 1.0,
    },
    "location": {
        "new york": 2.0,
        "nyc": 2.0,
        "remote": 1.5,
        "hybrid": 1.0,
    },
}
