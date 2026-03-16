"""Persona classification rules (EPIC 6).

Deterministic heuristics for BACKEND, PLATFORM_INFRA, HYBRID.
Tuning knobs: keyword weights, title signals, thresholds.
"""

# Title signals by persona (substring match, lowercase)
TITLE_SIGNALS = {
    "backend": [
        "backend",
        "backend engineer",
        "backend developer",
        "api engineer",
        "server",
        "software engineer",  # neutral but often backend
    ],
    "platform_infra": [
        "platform engineer",
        "infrastructure",
        "infra",
        "devops",
        "sre",
        "site reliability",
        "cloud engineer",
        "systems engineer",
    ],
    "hybrid": [
        "full stack",
        "fullstack",
        "full-stack",
    ],
}

# Description/tech keywords by persona (presence in combined text)
BACKEND_KEYWORDS = {
    "api": 2.0,
    "rest": 1.5,
    "graphql": 1.5,
    "database": 2.0,
    "postgresql": 1.5,
    "mysql": 1.5,
    "redis": 1.5,
    "mongodb": 1.0,
    "business logic": 2.0,
    "microservices": 1.5,
    "python": 1.0,
    "go": 1.0,
    "java": 1.0,
    "fastapi": 1.5,
    "django": 1.5,
    "flask": 1.0,
    "spring": 1.0,
    "rails": 1.0,
}

PLATFORM_INFRA_KEYWORDS = {
    "kubernetes": 2.5,
    "k8s": 2.5,
    "terraform": 2.0,
    "ansible": 1.5,
    "docker": 2.0,
    "ci/cd": 1.5,
    "cicd": 1.5,
    "observability": 2.0,
    "prometheus": 1.5,
    "grafana": 1.5,
    "datadog": 1.5,
    "aws": 1.5,
    "gcp": 1.5,
    "azure": 1.5,
    "google cloud": 1.5,
    "infrastructure as code": 2.0,
    "iac": 1.5,
}

# Score thresholds for confidence
CONFIDENCE_HIGH = 0.85
CONFIDENCE_MED = 0.65
CONFIDENCE_LOW = 0.45
