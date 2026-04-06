from __future__ import annotations

from typing import Any, Iterable

from bs4 import BeautifulSoup

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.public_boards.common import (
    BasePublicBoardSourceAdapter,
    PublicBoardCandidate,
    absolutize_url,
    clean_text,
    html_to_text,
    parse_date,
    parse_job_posting_json_ld,
)
from core.ingestion.types import AcquisitionRecord, SourcePolicy


class BuiltInNYCSourceAdapter(BasePublicBoardSourceAdapter):
    listing_url = "https://www.builtinnyc.com/jobs"

    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="builtin_nyc",
            policy=policy,
            backend=backend,
        )

    def extract_listings(self, *, html: str, page_record: AcquisitionRecord, **params: Any) -> Iterable[PublicBoardCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        max_results = int(params.get("max_results", 25))
        count = 0
        for link in soup.find_all("a", href=True, attrs={"data-id": "job-card-title"}):
            href = clean_text(link.get("href"))
            detail_url = absolutize_url(page_record.provenance.source_url, href)
            if not detail_url:
                continue
            job_id = clean_text(link.get("data-builtin-track-job-id"))
            card = link.find_parent("div", class_=lambda value: value and "job-bounded-responsive" in value)
            company = None
            summary = None
            if card is not None:
                company_link = card.find("a", href=lambda value: value and "/company/" in value)
                company = clean_text(company_link.get_text(" ", strip=True) if company_link else None)
                summary = clean_text(card.get_text(" ", strip=True))

            yield PublicBoardCandidate(
                external_id=job_id or detail_url.rstrip("/").split("/")[-1],
                source_url=detail_url,
                title=clean_text(link.get_text(" ", strip=True)),
                company=company,
                location=None,
                detail_url=detail_url,
                raw_listing={
                    "href": href,
                    "job_id": job_id,
                    "company": company,
                    "summary": summary,
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
        job_posting = parse_job_posting_json_ld(soup) or {}
        title = clean_text(job_posting.get("title")) or candidate.title
        company = candidate.company
        hiring_org = job_posting.get("hiringOrganization")
        if isinstance(hiring_org, dict):
            company = clean_text(hiring_org.get("name")) or company
        location = candidate.location
        locations = job_posting.get("jobLocation")
        if isinstance(locations, list) and locations:
            address = locations[0].get("address") if isinstance(locations[0], dict) else None
            if isinstance(address, dict):
                location = clean_text(
                    ", ".join(
                        part
                        for part in [
                            clean_text(address.get("addressLocality")),
                            clean_text(address.get("addressRegion")),
                            clean_text(address.get("addressCountry")),
                        ]
                        if part
                    )
                ) or location

        apply_link = None
        for anchor in soup.find_all("a", href=True):
            href = clean_text(anchor.get("href"))
            if href and any(provider in href for provider in ("greenhouse", "lever", "ashby", "workday")):
                apply_link = href
                break

        return PublicBoardCandidate(
            external_id=candidate.external_id,
            source_url=candidate.source_url,
            title=title,
            company=company,
            location=location,
            description=html_to_text(job_posting.get("description")) or candidate.description,
            apply_url=apply_link or candidate.apply_url,
            posted_at=parse_date(clean_text(job_posting.get("datePosted"))) or candidate.posted_at,
            employment_type=clean_text(job_posting.get("employmentType")) or candidate.employment_type,
            detail_url=candidate.detail_url,
            raw_listing=dict(candidate.raw_listing),
            raw_detail={
                "job_posting": dict(job_posting) if isinstance(job_posting, dict) else {},
                "apply_url": apply_link,
            },
        )


def build_builtin_nyc_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> BuiltInNYCSourceAdapter:
    return BuiltInNYCSourceAdapter(policy=policy, backend=backend)
