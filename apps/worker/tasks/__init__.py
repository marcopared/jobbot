from apps.worker.tasks.scrape import scrape_jobspy
from apps.worker.tasks.score import score_jobs
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.resume import generate_grounded_resume_task
from apps.worker.tasks.notify import send_notification
from apps.worker.tasks.discovery import run_discovery
from apps.worker.tasks.generation import evaluate_generation_gate
from apps.worker.tasks.ingest import (
    ingest_ashby,
    ingest_greenhouse,
    ingest_lever,
    ingest_url,
)
from apps.worker.tasks.resolution import resolve_discovery_job

__all__ = [
    "scrape_jobspy",
    "score_jobs",
    "classify_jobs",
    "ats_match_resume",
    "generate_grounded_resume_task",
    "send_notification",
    "run_discovery",
    "evaluate_generation_gate",
    "resolve_discovery_job",
    "ingest_ashby",
    "ingest_greenhouse",
    "ingest_lever",
    "ingest_url",
]
