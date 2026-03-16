"""Tests for grounded bullet selection (EPIC 7)."""

import pytest

from core.inventory.types import Role, RoleBullet, Project, ProjectBullet, ExperienceInventory, Contact
from core.resumes.selection import (
    select_role_bullets,
    select_roles,
    select_projects,
    select_skills,
)


def _make_inventory(roles=None, projects=None, skills=None):
    return ExperienceInventory(
        version=1,
        contact=Contact(name="Test", email="test@example.com", location="NYC"),
        summary_variants={},
        skills=skills or ["Python", "Go", "Kubernetes", "PostgreSQL"],
        roles=roles or [],
        projects=projects or [],
        education=[],
    )


def test_select_role_bullets_orders_by_keyword_match():
    role = Role(
        company="Acme",
        title="Engineer",
        bullets=[
            RoleBullet(text="Did X with Java", tags=["java"], metrics=[]),
            RoleBullet(text="Built Y with Python and Go", tags=["python", "go"], metrics=[]),
        ],
    )
    keywords = {"python", "go"}
    result = select_role_bullets(role, keywords, "BACKEND", max_bullets=5)
    assert len(result) == 2
    assert result[0] == "Built Y with Python and Go"
    assert result[1] == "Did X with Java"


def test_select_roles_returns_ordered_roles():
    r1 = Role(
        company="A",
        title="Engineer",
        bullets=[
            RoleBullet(text="Python work", tags=["python"], metrics=[]),
        ],
    )
    r2 = Role(
        company="B",
        title="Engineer",
        bullets=[
            RoleBullet(text="Go and K8s", tags=["go", "kubernetes"], metrics=[]),
        ],
    )
    inv = _make_inventory(roles=[r1, r2])
    result = select_roles(inv, {"python", "go", "kubernetes"}, "PLATFORM_INFRA", max_roles=2)
    assert len(result) >= 1
    assert all(isinstance(r[0], Role) and isinstance(r[1], list) for r in result)


def test_select_skills_front_loads_keywords():
    inv = _make_inventory(skills=["Ruby", "Python", "Java", "Go"])
    result = select_skills(inv, {"python", "go"}, max_skills=10)
    assert result[:2] == ["Python", "Go"]


def test_select_projects_empty_when_no_projects():
    inv = _make_inventory()
    result = select_projects(inv, set(), "BACKEND")
    assert result == []
