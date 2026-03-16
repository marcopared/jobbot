SYNONYM_MAP: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "gcp": "google cloud",
    "react.js": "react",
    "node.js": "nodejs",
    "vue.js": "vue",
}

TECH_KEYWORDS: dict[str, set[str]] = {
    "languages": {
        "python", "javascript", "typescript", "go", "java",
        "rust", "ruby", "c++", "scala", "kotlin",
    },
    "frameworks": {
        "fastapi", "django", "flask", "react", "nextjs",
        "express", "spring", "rails", "angular", "vue",
    },
    "databases": {
        "postgresql", "mysql", "mongodb", "redis",
        "elasticsearch", "dynamodb", "cassandra",
    },
    "cloud": {
        "aws", "google cloud", "azure", "docker",
        "kubernetes", "terraform", "ansible",
    },
    "tools": {
        "git", "jenkins", "github actions", "datadog",
        "grafana", "kafka", "rabbitmq", "celery",
    },
}


def normalize_keyword(kw: str) -> str:
    kw = kw.strip().lower()
    return SYNONYM_MAP.get(kw, kw)


def extract_keywords(text: str) -> set[str]:
    """Extract known tech keywords from text, with synonym normalization. Uses word-boundary matching."""
    from core.matching import keyword_in_text

    found: set[str] = set()
    all_keywords = set().union(*TECH_KEYWORDS.values())
    for kw in all_keywords:
        if keyword_in_text(text, kw):
            found.add(kw)
    for synonym, canonical in SYNONYM_MAP.items():
        if keyword_in_text(text, synonym):
            found.add(canonical)
    return found
