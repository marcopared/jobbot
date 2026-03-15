"""Load and validate experience inventory from YAML (EPIC 7)."""

import hashlib
import logging
from pathlib import Path

import yaml

from core.inventory.types import (
    Contact,
    ExperienceInventory,
    Project,
    ProjectBullet,
    Role,
    RoleBullet,
)

logger = logging.getLogger(__name__)


def _ensure_list(val, default=None):
    if val is None:
        return default or []
    return list(val) if isinstance(val, (list, tuple)) else [val]


def _parse_bullet(b: dict | str) -> RoleBullet | ProjectBullet:
    """Parse bullet from dict or string."""
    if isinstance(b, str):
        return RoleBullet(text=b, tags=[], metrics=[])
    text = b.get("text", str(b))
    tags = _ensure_list(b.get("tags"))
    metrics = _ensure_list(b.get("metrics"))
    return RoleBullet(text=text, tags=tags, metrics=metrics)


def _parse_role(r: dict) -> Role:
    bullets = [_parse_bullet(b) for b in _ensure_list(r.get("bullets"))]
    return Role(
        company=str(r.get("company", "")),
        title=str(r.get("title", "")),
        location=str(r.get("location", "")),
        start=str(r.get("start", "")),
        end=str(r.get("end", "present")),
        bullets=bullets,
        tags=_ensure_list(r.get("tags")),
    )


def _parse_project(p: dict) -> Project:
    bullets_raw = _ensure_list(p.get("bullets"))
    bullets = []
    for b in bullets_raw:
        if isinstance(b, dict):
            bullets.append(
                ProjectBullet(
                    text=b.get("text", ""),
                    tags=_ensure_list(b.get("tags")),
                    metrics=_ensure_list(b.get("metrics")),
                )
            )
        else:
            bullets.append(ProjectBullet(text=str(b), tags=[], metrics=[]))
    return Project(
        name=str(p.get("name", "")),
        description=str(p.get("description", "")),
        url=p.get("url"),
        bullets=bullets,
    )


def load_inventory(path: str | Path) -> ExperienceInventory:
    """
    Load and validate experience inventory from YAML.

    Raises FileNotFoundError if path does not exist.
    Raises ValueError on schema validation failure.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Experience inventory not found: {path}")

    raw = p.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Inventory YAML must be a mapping")

    version = data.get("version", 1)
    contact_data = data.get("contact") or {}
    contact = Contact(
        name=str(contact_data.get("name", "")),
        email=str(contact_data.get("email", "")),
        location=str(contact_data.get("location", "")),
        linkedin_url=contact_data.get("linkedin_url"),
    )

    summary_variants = data.get("summary_variants") or {}
    if isinstance(summary_variants, dict):
        summary_variants = {k: str(v) for k, v in summary_variants.items()}
    else:
        summary_variants = {}

    skills = [str(s) for s in _ensure_list(data.get("skills"))]

    roles = [_parse_role(r) for r in _ensure_list(data.get("roles"))]

    projects = [_parse_project(pr) for pr in _ensure_list(data.get("projects"))]

    education = _ensure_list(data.get("education"))
    education = [
        {"school": str(e.get("school", "")), "degree": str(e.get("degree", "")), "year": str(e.get("year", ""))}
        if isinstance(e, dict)
        else {"school": "", "degree": str(e), "year": ""}
        for e in education
    ]

    return ExperienceInventory(
        version=version,
        contact=contact,
        summary_variants=summary_variants,
        skills=skills,
        roles=roles,
        projects=projects,
        education=education,
        raw_yaml=raw,
    )


def compute_inventory_hash(inventory: ExperienceInventory) -> str:
    """Compute content hash of inventory for version tracking."""
    content = inventory.raw_yaml or ""
    if not content:
        parts = [
            str(inventory.version),
            str(inventory.contact),
            str(inventory.summary_variants),
            str(inventory.skills),
            str([(r.company, r.title, [b.text for b in r.bullets]) for r in inventory.roles]),
            str([(p.name, [b.text for b in p.bullets]) for p in inventory.projects]),
        ]
        content = "|".join(parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
