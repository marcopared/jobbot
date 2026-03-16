"""Types for the experience inventory YAML schema (EPIC 7)."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Contact:
    """Contact info block."""

    name: str = ""
    email: str = ""
    location: str = ""
    linkedin_url: Optional[str] = None


@dataclass
class RoleBullet:
    """Single bullet under a role. May have tags (persona alignment) and metrics."""

    text: str
    tags: list[str]  # e.g. ["backend", "python", "kubernetes"]
    metrics: list[str]  # e.g. ["40%", "50+"]


@dataclass
class Role:
    """Work experience role."""

    company: str
    title: str
    location: str = ""
    start: str = ""
    end: str = "present"
    bullets: list[RoleBullet] = None
    tags: list[str] = None  # Persona alignment at role level

    def __post_init__(self) -> None:
        if self.bullets is None:
            self.bullets = []
        if self.tags is None:
            self.tags = []


@dataclass
class ProjectBullet:
    """Single bullet under a project."""

    text: str
    tags: list[str]
    metrics: list[str]


@dataclass
class Project:
    """Side/open-source project."""

    name: str
    description: str = ""
    url: Optional[str] = None
    bullets: list[ProjectBullet] = None

    def __post_init__(self) -> None:
        if self.bullets is None:
            self.bullets = []


@dataclass
class ExperienceInventory:
    """Full experience inventory (parsed from YAML)."""

    version: int
    contact: Contact
    summary_variants: dict[str, str]  # persona -> summary text
    skills: list[str]
    roles: list[Role]
    projects: list[Project]
    education: list[dict]  # [{school, degree, year}]
    raw_yaml: Optional[str] = None  # For hash computation
