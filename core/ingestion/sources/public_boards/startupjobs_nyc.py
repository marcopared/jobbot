from __future__ import annotations

from typing import Any, Iterable

from bs4 import BeautifulSoup

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.public_boards.common import (
    BasePublicBoardSourceAdapter,
    PublicBoardCandidate,
    absolutize_url,
    clean_text,
    collapse_spaced_letters,
    parse_date,
)
from core.ingestion.types import AcquisitionRecord, SourcePolicy


class StartupJobsNYCSourceAdapter(BasePublicBoardSourceAdapter):
    listing_url = "https://startupjobs.nyc/"

    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="startupjobs_nyc",
            policy=policy,
            backend=backend,
        )

    def extract_listings(self, *, html: str, page_record: AcquisitionRecord, **params: Any) -> Iterable[PublicBoardCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        max_results = int(params.get("max_results", 25))
        count = 0
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href or "/jobs/" not in href:
                continue
            title_node = anchor.select_one('[data-framer-name="Job Title"]')
            company_node = anchor.select_one('[data-framer-name="Company"]')
            location_node = anchor.select_one('[data-framer-name="Job Location"]')
            posted_at_node = anchor.select_one('[data-framer-name="Date"]')
            title = clean_text(title_node.get_text(" ", strip=True) if title_node else None)
            company = clean_text(company_node.get_text(" ", strip=True) if company_node else None)
            location = clean_text(location_node.get_text(" ", strip=True) if location_node else None)
            posted_at_text = clean_text(posted_at_node.get_text(" ", strip=True) if posted_at_node else None)
            detail_url = absolutize_url(page_record.provenance.source_url, href)
            if not detail_url:
                continue
            yield PublicBoardCandidate(
                external_id=detail_url.rstrip("/").split("/")[-1],
                source_url=detail_url,
                title=title,
                company=company,
                location=location,
                posted_at=parse_date(posted_at_text, "%b %d, %Y"),
                detail_url=detail_url,
                raw_listing={
                    "href": href,
                    "title": title,
                    "company": company,
                    "location": location,
                    "posted_at": posted_at_text,
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
        title = candidate.title or collapse_spaced_letters(
            soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else None
        )
        company_node = soup.find("h3")
        company = clean_text(company_node.get_text(" ", strip=True) if company_node else candidate.company)

        detail_texts = [
            clean_text(node.get_text(" ", strip=True))
            for node in soup.find_all("p")
        ]
        detail_texts = [text for text in detail_texts if text]
        posted_at = candidate.posted_at

        location = candidate.location
        for index, text in enumerate(detail_texts):
            if text == "Published on":
                candidate_date = parse_date(detail_texts[index + 1] if index + 1 < len(detail_texts) else None, "%b %d, %Y")
                if candidate_date and posted_at is None:
                    posted_at = candidate_date
            if text == "/" or text in {"Visit Company Website", "Apply For This Job", "Published on"}:
                continue
            if text and any(marker in text for marker in ("United States", "USA", "Remote")) and location is None:
                location = text

        apply_link = None
        for anchor in soup.find_all("a", href=True):
            text = clean_text(anchor.get_text(" ", strip=True))
            if text == "Apply For This Job":
                apply_link = clean_text(anchor.get("href"))
                break

        description_parts: list[str] = []
        description_heading = soup.find(lambda tag: tag.name in {"h2", "h3"} and clean_text(tag.get_text(" ", strip=True)) in {"About the Role", "About", "Job Description"})
        if description_heading is not None:
            for sibling in description_heading.find_all_next(["p", "li", "h2", "h3"]):
                if sibling.name in {"h2", "h3"} and sibling is not description_heading:
                    break
                text = clean_text(sibling.get_text(" ", strip=True))
                if text and text not in {"Apply For This Job", "Visit Company Website"}:
                    description_parts.append(text)

        return PublicBoardCandidate(
            external_id=candidate.external_id,
            source_url=candidate.source_url,
            title=title or candidate.title,
            company=company or candidate.company,
            location=location or candidate.location,
            description=" ".join(description_parts) or candidate.description,
            apply_url=apply_link or candidate.apply_url,
            posted_at=posted_at,
            employment_type=candidate.employment_type,
            detail_url=candidate.detail_url,
            raw_listing=dict(candidate.raw_listing),
            raw_detail={
                "title": title,
                "company": company,
                "location": location,
                "apply_url": apply_link,
            },
        )


def build_startupjobs_nyc_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> StartupJobsNYCSourceAdapter:
    return StartupJobsNYCSourceAdapter(policy=policy, backend=backend)
