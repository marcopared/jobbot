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


class YCJobsSourceAdapter(BaseAuthBoardSourceAdapter):
    listing_url = "https://www.workatastartup.com/jobs"

    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="yc",
            policy=policy,
            backend=backend,
        )

    def extract_listings(self, *, html: str, page_record: AcquisitionRecord, **params: Any) -> Iterable[PublicBoardCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        max_results = int(params.get("max_results", 25))
        count = 0
        for card in soup.select("[data-testid='JobRow'], .job-row"):
            anchor = card.select_one("a[href]")
            detail_url = absolutize_url(page_record.provenance.source_url, anchor.get("href") if anchor else None)
            if not detail_url:
                continue
            title = clean_text(anchor.get_text(" ", strip=True) if anchor else None)
            company = clean_text(
                (card.select_one("[data-testid='company-name']") or card.select_one(".company-name")).get_text(" ", strip=True)
                if (card.select_one("[data-testid='company-name']") or card.select_one(".company-name"))
                else None
            )
            location = clean_text(
                (card.select_one("[data-testid='location']") or card.select_one(".location")).get_text(" ", strip=True)
                if (card.select_one("[data-testid='location']") or card.select_one(".location"))
                else None
            )
            time_node = card.select_one("time[datetime]")
            external_id = clean_text(card.get("data-job-id")) or detail_url.rstrip("/").split("/")[-1]
            yield PublicBoardCandidate(
                external_id=external_id,
                source_url=detail_url,
                title=title,
                company=company,
                location=location,
                posted_at=parse_date(clean_text(time_node.get("datetime")) if time_node else None),
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
            (soup.select_one("[data-testid='job-title']") or soup.find("h1")).get_text(" ", strip=True)
            if (soup.select_one("[data-testid='job-title']") or soup.find("h1"))
            else None
        ) or candidate.title
        company = clean_text(
            (soup.select_one("[data-testid='company-link']") or soup.select_one(".company-name")).get_text(" ", strip=True)
            if (soup.select_one("[data-testid='company-link']") or soup.select_one(".company-name"))
            else None
        ) or candidate.company
        location = clean_text(
            (soup.select_one("[data-testid='job-location']") or soup.select_one(".location")).get_text(" ", strip=True)
            if (soup.select_one("[data-testid='job-location']") or soup.select_one(".location"))
            else None
        ) or candidate.location
        description_node = soup.select_one("[data-testid='job-description']") or soup.select_one(".job-description")
        apply_link = soup.select_one("[data-testid='apply-button'][href]") or soup.select_one("a.apply-button[href]")
        employment_type = clean_text(
            (soup.select_one("[data-testid='employment-type']") or soup.select_one(".employment-type"))
            .get_text(" ", strip=True)
            if (soup.select_one("[data-testid='employment-type']") or soup.select_one(".employment-type"))
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


def build_yc_jobs_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> YCJobsSourceAdapter:
    return YCJobsSourceAdapter(policy=policy, backend=backend)
