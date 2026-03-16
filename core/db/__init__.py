"""Canonical DB surface for JobBot v1.

Exports models and helpers used by the active job pipeline (ingest → score → classify →
ATS → resume). Legacy apply-flow tables (Application, Intervention) remain in
core.db.models for schema compatibility but are not re-exported here.
"""
from core.db.base import Base
from core.db.models import (
    Artifact,
    Company,
    Job,
    JobAnalysis,
    JobSourceRecord,
    ScrapeRun,
)
from core.db.session import async_engine, async_session_factory, get_db

__all__ = [
    "Artifact",
    "Base",
    "Company",
    "Job",
    "JobAnalysis",
    "JobSourceRecord",
    "ScrapeRun",
    "async_engine",
    "async_session_factory",
    "get_db",
]
