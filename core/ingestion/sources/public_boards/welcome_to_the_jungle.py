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


class WelcomeToTheJungleSourceAdapter(BasePublicBoardSourceAdapter):
    listing_url = "https://www.welcometothejungle.com/en/jobs"

    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="welcome_to_the_jungle",
            policy=policy,
            backend=backend,
        )

    def extract_listings(self, *, html: str, page_record: AcquisitionRecord, **params: Any) -> Iterable[PublicBoardCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        max_results = int(params.get("max_results", 25))
        seen: set[str] = set()
        count = 0
        for link in soup.find_all("a", href=True, attrs={"aria-label": True}):
            href = clean_text(link.get("href"))
            if not href or "/jobs/" not in href or href in seen:
                continue
            seen.add(href)
            detail_url = absolutize_url(page_record.provenance.source_url, href)
            card = link.find_parent(["div", "li"])
            card_text = clean_text(card.get_text(" ", strip=True) if card else None) or ""
            company = None
            title = clean_text(link.get("aria-label", "").replace("Visit the job post for", ""))
            if card:
                texts = [clean_text(node.get_text(" ", strip=True)) for node in card.find_all(["h2", "h3", "p", "span"], limit=8)]
                texts = [text for text in texts if text]
                if len(texts) >= 2:
                    company = texts[1]
            yield PublicBoardCandidate(
                external_id=href.strip("/"),
                source_url=detail_url,
                title=title,
                company=company,
                location=None,
                detail_url=detail_url,
                raw_listing={
                    "href": href,
                    "card_text": card_text,
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
        job_locations = job_posting.get("jobLocation")
        if isinstance(job_locations, list) and job_locations:
            place = job_locations[0]
            if isinstance(place, dict):
                address = place.get("address")
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

        return PublicBoardCandidate(
            external_id=candidate.external_id,
            source_url=candidate.source_url,
            title=title,
            company=company,
            location=location,
            description=html_to_text(job_posting.get("description")) or candidate.description,
            apply_url=candidate.source_url,
            posted_at=parse_date(clean_text(job_posting.get("datePosted"))) or candidate.posted_at,
            employment_type=clean_text(job_posting.get("employmentType")) or candidate.employment_type,
            detail_url=candidate.detail_url,
            raw_listing=dict(candidate.raw_listing),
            raw_detail={
                "job_posting": dict(job_posting) if isinstance(job_posting, dict) else {},
            },
        )


def build_welcome_to_the_jungle_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> WelcomeToTheJungleSourceAdapter:
    return WelcomeToTheJungleSourceAdapter(policy=policy, backend=backend)
