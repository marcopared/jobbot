"""Experience inventory (EPIC 7). Version-controlled YAML as source of truth."""

from core.inventory.loader import load_inventory, compute_inventory_hash
from core.inventory.types import (
    ExperienceInventory,
    RoleBullet,
    ProjectBullet,
    Role,
    Project,
    Contact,
)

__all__ = [
    "load_inventory",
    "compute_inventory_hash",
    "ExperienceInventory",
    "RoleBullet",
    "ProjectBullet",
    "Role",
    "Project",
    "Contact",
]
