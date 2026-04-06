from __future__ import annotations

from typing import Any, Iterable

from bs4 import BeautifulSoup

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.auth_boards.common import BaseAuthBoardSourceAdapter
from core.ingestion.sources.public_boards.common import (
    PublicBoardCandidate,
    absolutize_url,
    clean_text,
    html_to_text,
    parse_date,
)
from core.ingestion.types import AcquisitionRecord, SourcePolicy


class LinkedInJobsSourceAdapter(BaseAuthBoardSourceAdapter):
    listing_url = "https://www.linkedin.com/jobs/search/"

    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="linkedin_jobs",
            policy=policy,
            backend=backend,
        )

    def extract_listings(self, *, html: str, page_record: AcquisitionRecord, **params: Any) -> Iterable[PublicBoardCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        max_results = int(params.get("max_results", 25))
        count = 0
        for card in soup.select("li[data-job-id], div[data-job-id]"):
            detail_anchor = card.select_one("a.base-card__full-link[href], a[data-control-name='job_card_click'][href]")
            detail_url = absolutize_url(
                page_record.provenance.source_url,
                detail_anchor.get("href") if detail_anchor else None,
            )
            if not detail_url:
                continue
            external_id = clean_text(card.get("data-job-id")) or detail_url.rstrip("/").split("/")[-1]
            title = clean_text(
                (card.select_one(".base-search-card__title") or card.select_one("h3")).get_text(" ", strip=True)
                if (card.select_one(".base-search-card__title") or card.select_one("h3"))
                else None
            )
            company = clean_text(
                (card.select_one(".base-search-card__subtitle") or card.select_one("h4")).get_text(" ", strip=True)
                if (card.select_one(".base-search-card__subtitle") or card.select_one("h4"))
                else None
            )
            location = clean_text(
                (card.select_one(".job-search-card__location") or card.select_one(".job-search-card__listdate"))
                .get_text(" ", strip=True)
                if (card.select_one(".job-search-card__location") or card.select_one(".job-search-card__listdate"))
                else None
            )
            time_node = card.select_one("time[datetime]")
            posted_at = parse_date(clean_text(time_node.get("datetime")) if time_node else None)
            yield PublicBoardCandidate(
                external_id=external_id,
                source_url=detail_url,
                title=title,
                company=company,
                location=location,
                posted_at=posted_at,
                detail_url=detail_url,
                raw_listing={
                    "job_id": external_id,
                    "detail_url": detail_url,
                    "title": title,
                    "company": company,
                    "location": location,
                },
            )
            count += 1
            if count >= max_results:
                break

    def enrich_candidate(
        self,
        *,
        candidate: PublicBoardCandidate,
        detail_record: AcquisitionRecord | None,
    ) -> PublicBoardCandidate:
        if detail_record is None:
            return candidate

        soup = BeautifulSoup(detail_record.artifact.content or "", "html.parser")
        title = clean_text(
            (soup.select_one(".top-card-layout__title") or soup.find("h1")).get_text(" ", strip=True)
            if (soup.select_one(".top-card-layout__title") or soup.find("h1"))
            else None
        ) or candidate.title
        company = clean_text(
            (soup.select_one(".topcard__org-name-link") or soup.select_one(".topcard__flavor"))
            .get_text(" ", strip=True)
            if (soup.select_one(".topcard__org-name-link") or soup.select_one(".topcard__flavor"))
            else None
        ) or candidate.company
        location = clean_text(
            (soup.select_one(".topcard__flavor--bullet") or soup.select_one(".job-details-jobs-unified-top-card__primary-description-container"))
            .get_text(" ", strip=True)
            if (
                soup.select_one(".topcard__flavor--bullet")
                or soup.select_one(".job-details-jobs-unified-top-card__primary-description-container")
            )
            else None
        ) or candidate.location
        description_node = soup.select_one(".show-more-less-html__markup") or soup.select_one(".description__text")
        apply_link = soup.select_one("a[data-tracking-control-name='public_jobs_topcard-apply-link'][href]") or soup.select_one("a.topcard__link[href]")
        employment_type = clean_text(
            (soup.select_one(".description__job-criteria-text") or soup.select_one("[data-test-id='job-criteria-employment-type']"))
            .get_text(" ", strip=True)
            if (
                soup.select_one(".description__job-criteria-text")
                or soup.select_one("[data-test-id='job-criteria-employment-type']")
            )
            else None
        )
        time_node = soup.select_one("time[datetime]")

        return PublicBoardCandidate(
            external_id=candidate.external_id,
            source_url=candidate.source_url,
            title=title,
            company=company,
            location=location,
            description=html_to_text(str(description_node)) if description_node is not None else candidate.description,
            apply_url=clean_text(apply_link.get("href")) if apply_link else candidate.apply_url,
            posted_at=parse_date(clean_text(time_node.get("datetime")) if time_node else None) or candidate.posted_at,
            employment_type=employment_type or candidate.employment_type,
            detail_url=candidate.detail_url,
            raw_listing=dict(candidate.raw_listing),
            raw_detail={
                "title": title,
                "company": company,
                "location": location,
                "apply_url": clean_text(apply_link.get("href")) if apply_link else None,
                "employment_type": employment_type,
            },
        )


def build_linkedin_jobs_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> LinkedInJobsSourceAdapter:
    return LinkedInJobsSourceAdapter(policy=policy, backend=backend)
