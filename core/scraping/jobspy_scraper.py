from datetime import date, datetime
from typing import Optional

import logging
import pandas as pd

from jobspy import scrape_jobs

from apps.api.settings import Settings
from core.db.models import JobSource
from core.scraping.base import (
    NormalizedJob,
    ScrapeParams,
    ScrapeResult,
)

logger = logging.getLogger(__name__)
settings = Settings()


def _to_json_compatible(value):
    if isinstance(value, dict):
        return {str(k): _to_json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(v) for v in value]
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _sanitize_row_payload(row: pd.Series) -> dict:
    return {k: _to_json_compatible(v) for k, v in row.to_dict().items()}


def dataframe_to_normalized_jobs(df: pd.DataFrame) -> list[NormalizedJob]:
    """Convert jobspy DataFrame rows to NormalizedJob objects."""
    jobs: list[NormalizedJob] = []
    for _, row in df.iterrows():
        title = str(row.get("title", "") or "").strip()
        company_name = str(row.get("company", "") or "").strip()
        url = str(row.get("job_url", "") or "").strip()
        if not title or not url:
            continue
        apply_url = row.get("job_url_direct")
        apply_url = str(apply_url).strip() if pd.notna(apply_url) and apply_url else None
        location = row.get("location")
        location = str(location).strip() if pd.notna(location) and location else None
        description = row.get("description")
        description = str(description).strip() if pd.notna(description) and description else None
        min_amt = row.get("min_amount")
        salary_min = int(min_amt) if pd.notna(min_amt) and min_amt is not None else None
        max_amt = row.get("max_amount")
        salary_max = int(max_amt) if pd.notna(max_amt) and max_amt is not None else None
        date_posted = row.get("date_posted")
        posted_at: Optional[datetime] = None
        if pd.notna(date_posted) and date_posted is not None:
            if isinstance(date_posted, date) and not isinstance(date_posted, datetime):
                posted_at = datetime.combine(date_posted, datetime.min.time())
            elif isinstance(date_posted, datetime):
                posted_at = date_posted
        is_remote = bool(row.get("is_remote", False)) if pd.notna(row.get("is_remote")) else False
        source_job_id = row.get("id")
        source_job_id = str(source_job_id) if pd.notna(source_job_id) and source_job_id else None
        raw_payload = _sanitize_row_payload(row)
        jobs.append(
            NormalizedJob(
                title=title,
                company_name=company_name,
                location=location,
                url=url,
                apply_url=apply_url,
                description=description,
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=posted_at,
                remote_flag=is_remote,
                source=JobSource.JOBSPY,
                source_job_id=source_job_id,
                raw_payload=raw_payload,
            )
        )
    return jobs


class JobSpyScraper:
    """JobSpy wrapper implementing scrape logic."""

    def scrape(self, params: ScrapeParams) -> ScrapeResult:
        sites = ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]
        if params.results_wanted <= 15:
            sites = ["google", "indeed"]

        logger.info(
            "Starting JobSpy scrape: query=%s location=%s results_wanted=%s",
            params.query,
            params.location,
            params.results_wanted,
        )
        logger.debug("JobSpy sites selected: %s", sites)

        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=params.query,
                location=params.location,
                hours_old=params.hours_old or 168,
                results_wanted=params.results_wanted,
                linkedin_fetch_description=params.results_wanted <= 25,
                country_indeed="USA",
            )
            logger.info("JobSpy fetched %s rows", len(df) if df is not None else 0)
            logger.debug("JobSpy dataframe columns: %s", list(df.columns) if df is not None else None)
        except Exception as e:
            logger.exception("JobSpy scrape failed for query=%s location=%s", params.query, params.location)
            return ScrapeResult(
                jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=str(e),
            )

        if df is None or df.empty:
            logger.info("JobSpy returned no results for query=%s location=%s", params.query, params.location)
            return ScrapeResult(
                jobs=[],
                stats={"fetched": 0, "errors": 0},
                error=None,
            )

        jobs = dataframe_to_normalized_jobs(df)
        logger.info("Normalized %s jobs from JobSpy (fetched=%s)", len(jobs), len(df))
        return ScrapeResult(
            jobs=jobs,
            stats={"fetched": len(df), "errors": 0},
            error=None,
        )
