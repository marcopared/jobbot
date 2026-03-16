"""Tests for experience inventory loader and schema (EPIC 7)."""

import tempfile
from pathlib import Path

import pytest

from core.inventory.loader import compute_inventory_hash, load_inventory
from core.inventory.types import Contact, ExperienceInventory, Role, RoleBullet


def test_load_inventory_minimal():
    """Load minimal valid inventory."""
    yaml_content = """
version: 1
contact:
  name: Jane Doe
  email: jane@example.com
  location: NYC
summary_variants:
  BACKEND: "Backend engineer summary"
  HYBRID: "Hybrid summary"
skills:
  - Python
  - Go
roles: []
projects: []
education: []
"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        f.write(yaml_content.encode())
        path = f.name
    try:
        inv = load_inventory(path)
        assert inv.version == 1
        assert inv.contact.name == "Jane Doe"
        assert inv.contact.email == "jane@example.com"
        assert inv.summary_variants["BACKEND"] == "Backend engineer summary"
        assert inv.skills == ["Python", "Go"]
        assert inv.roles == []
        assert inv.projects == []
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_inventory_with_roles():
    """Load inventory with roles and bullets."""
    yaml_content = """
version: 1
contact:
  name: Jane
  email: j@ex.com
summary_variants: {}
skills: []
roles:
  - company: Acme
    title: Engineer
    start: "2020-01"
    end: present
    bullets:
      - text: Built APIs with Python
        tags: [backend, python]
        metrics: ["40%"]
projects: []
education: []
"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        f.write(yaml_content.encode())
        path = f.name
    try:
        inv = load_inventory(path)
        assert len(inv.roles) == 1
        r = inv.roles[0]
        assert r.company == "Acme"
        assert r.title == "Engineer"
        assert len(r.bullets) == 1
        assert r.bullets[0].text == "Built APIs with Python"
        assert r.bullets[0].tags == ["backend", "python"]
        assert r.bullets[0].metrics == ["40%"]
    finally:
        Path(path).unlink(missing_ok=True)


def test_load_inventory_not_found():
    """Raise FileNotFoundError when path does not exist."""
    with pytest.raises(FileNotFoundError):
        load_inventory("/nonexistent/path.yaml")


def test_load_inventory_invalid_yaml():
    """Raise ValueError for invalid YAML."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        f.write(b"invalid: yaml: [")
        path = f.name
    try:
        with pytest.raises(ValueError):
            load_inventory(path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_compute_inventory_hash():
    """Hash is deterministic and changes with content."""
    yaml1 = """
version: 1
contact: {name: A, email: a@x.com}
summary_variants: {}
skills: [Python]
roles: []
projects: []
education: []
"""
    yaml2 = """
version: 1
contact: {name: A, email: a@x.com}
summary_variants: {}
skills: [Python, Go]
roles: []
projects: []
education: []
"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f1:
        f1.write(yaml1.encode())
        p1 = f1.name
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f2:
        f2.write(yaml2.encode())
        p2 = f2.name
    try:
        inv1 = load_inventory(p1)
        inv2 = load_inventory(p2)
        h1 = compute_inventory_hash(inv1)
        h2 = compute_inventory_hash(inv2)
        assert h1 != h2
        assert len(h1) == 16
        assert len(h2) == 16
        # Same content -> same hash
        inv1b = load_inventory(p1)
        assert compute_inventory_hash(inv1b) == h1
    finally:
        Path(p1).unlink(missing_ok=True)
        Path(p2).unlink(missing_ok=True)
