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


def test_java_not_matched_in_javascript_bullet():
    """Word-boundary: bullet about JavaScript must not match keyword 'java'."""
    role = Role(
        company="Acme",
        title="Engineer",
        bullets=[
            RoleBullet(text="Built frontend with JavaScript and TypeScript.", tags=[], metrics=[]),
            RoleBullet(text="Backend in Java and Spring.", tags=["java"], metrics=[]),
        ],
    )
    keywords = {"java"}
    result = select_role_bullets(role, keywords, "BACKEND", max_bullets=5)
    # Java bullet should rank first; JavaScript bullet should not get 'java' credit from substring
    assert result[0] == "Backend in Java and Spring."
    assert result[1] == "Built frontend with JavaScript and TypeScript."


def test_go_not_matched_in_going_or_goal_bullet():
    """Word-boundary: 'going' or 'goal' must not match keyword 'go'."""
    role = Role(
        company="Acme",
        title="Engineer",
        bullets=[
            RoleBullet(text="Going forward we will migrate.", tags=[], metrics=[]),
            RoleBullet(text="Built services in Go.", tags=["go"], metrics=[]),
        ],
    )
    keywords = {"go"}
    result = select_role_bullets(role, keywords, "BACKEND", max_bullets=5)
    assert result[0] == "Built services in Go."
    assert result[1] == "Going forward we will migrate."


def test_sql_not_matched_in_postgresql_bullet():
    """Word-boundary: 'postgresql' must not match keyword 'sql' (no false positive)."""
    role = Role(
        company="Acme",
        title="Engineer",
        bullets=[
            RoleBullet(text="Used PostgreSQL and NoSQL.", tags=[], metrics=[]),
            RoleBullet(text="Wrote SQL queries for reporting.", tags=["sql"], metrics=[]),
        ],
    )
    keywords = {"sql"}
    result = select_role_bullets(role, keywords, "BACKEND", max_bullets=5)
    # SQL bullet should rank first; PostgreSQL/NoSQL should not match 'sql'
    assert result[0] == "Wrote SQL queries for reporting."


def test_phrase_software_engineer_matches_bullet():
    """Multi-word phrase 'software engineer' matches as whole phrase."""
    role = Role(
        company="Acme",
        title="Engineer",
        bullets=[
            RoleBullet(text="Worked as software engineer on APIs.", tags=[], metrics=[]),
            RoleBullet(text="General engineering work.", tags=[], metrics=[]),
        ],
    )
    keywords = {"software engineer"}
    result = select_role_bullets(role, keywords, "BACKEND", max_bullets=5)
    assert result[0] == "Worked as software engineer on APIs."


def test_phrase_google_cloud_matches_bullet():
    """Multi-word phrase 'google cloud' matches with flexible whitespace."""
    role = Role(
        company="Acme",
        title="Engineer",
        bullets=[
            RoleBullet(text="Deployed on Google Cloud Platform.", tags=[], metrics=[]),
        ],
    )
    keywords = {"google cloud"}
    result = select_role_bullets(role, keywords, "PLATFORM_INFRA", max_bullets=5)
    assert len(result) == 1
    assert "Google Cloud" in result[0]
