"""Regression tests for run-item contract between backend writers and UI.

Verifies that items_json produced by all ingestion paths conforms to the
canonical RunItem schema expected by the UI (RunDetailPage.tsx / api.ts).

Canonical fields: index, outcome, job_id, dedup_hash, source, source_job_id,
title, company_name, location, url, apply_url, ats_type, raw_payload_json.
"""

import uuid

import httpx
import pytest
from httpx import ASGITransport

from apps.api.main import app
from core.db.models import ScrapeRun, ScrapeRunStatus
from core.db.session import get_sync_session

CANONICAL_FIELDS = {
    "index",
    "outcome",
    "job_id",
    "dedup_hash",
    "source",
    "source_job_id",
    "title",
    "company_name",
    "location",
    "url",
    "apply_url",
    "ats_type",
    "raw_payload_json",
}


def _make_run(source: str, items_json: list[dict]) -> str:
    """Insert a ScrapeRun with given items_json. Returns run_id as string."""
    with get_sync_session() as session:
        run = ScrapeRun(
            source=source,
            status=ScrapeRunStatus.SUCCESS.value,
            stats_json={"fetched": len(items_json), "inserted": len(items_json), "duplicates": 0, "errors": 0},
            items_json=items_json,
        )
        session.add(run)
        session.commit()
        return str(run.id)


JOBSPY_ITEM = {
    "index": 1,
    "outcome": "inserted",
    "dedup_reason": "new",
    "job_id": str(uuid.uuid4()),
    "dedup_hash": "abc123",
    "source": "indeed",
    "source_job_id": "ext-123",
    "title": "Backend Engineer",
    "company_name": "Acme Corp",
    "location": "Remote",
    "url": "https://indeed.com/job/123",
    "apply_url": "https://indeed.com/apply/123",
    "ats_type": "indeed",
    "raw_payload_json": {"salary": "100k"},
}

GREENHOUSE_ITEM = {
    "index": 1,
    "outcome": "inserted",
    "dedup_reason": "inserted",
    "job_id": str(uuid.uuid4()),
    "dedup_hash": "def456",
    "source": "greenhouse",
    "source_job_id": "gh-456",
    "title": "Frontend Developer",
    "company_name": "Widget Inc",
    "location": "San Francisco, CA",
    "url": "https://boards.greenhouse.io/widget/jobs/456",
    "apply_url": "https://boards.greenhouse.io/widget/jobs/456#app",
    "ats_type": "greenhouse",
    "raw_payload_json": {"id": 456, "departments": [{"name": "Engineering"}]},
}

DISCOVERY_ITEM = {
    "index": 1,
    "outcome": "inserted",
    "dedup_reason": "inserted",
    "job_id": str(uuid.uuid4()),
    "dedup_hash": "ghi789",
    "source": "agg1",
    "source_job_id": "adzuna-789",
    "title": "Data Scientist",
    "company_name": "DataCo",
    "location": "New York, NY",
    "url": "https://adzuna.com/job/789",
    "apply_url": "https://adzuna.com/apply/789",
    "ats_type": "agg1",
    "raw_payload_json": {"category": {"tag": "data-science"}},
    "source_confidence": 0.7,
}

MANUAL_INTAKE_ITEM = {
    "index": 1,
    "outcome": "inserted",
    "job_id": str(uuid.uuid4()),
    "dedup_hash": "manual001",
    "source": "manual_intake",
    "source_job_id": None,
    "title": "Product Manager",
    "company_name": "StartupX",
    "location": "Austin, TX",
    "url": "https://startupx.com/jobs/pm",
    "apply_url": "https://startupx.com/apply/pm",
    "ats_type": "manual_intake",
    "raw_payload_json": None,
}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.parametrize(
    "label,source,item",
    [
        ("jobspy", "jobspy", JOBSPY_ITEM),
        ("greenhouse", "greenhouse", GREENHOUSE_ITEM),
        ("discovery_agg1", "agg1", DISCOVERY_ITEM),
        ("manual_intake", "manual_intake", MANUAL_INTAKE_ITEM),
    ],
)
async def test_run_item_has_canonical_fields(client, label, source, item):
    """Each ingestion path produces items with the full canonical field set."""
    run_id = _make_run(source, [item])
    resp = await client.get(f"/api/runs/{run_id}/items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["counts"]["all"] == 1

    returned_item = data["items"][0]
    missing = CANONICAL_FIELDS - set(returned_item.keys())
    assert not missing, f"[{label}] Missing canonical fields: {missing}"

    # Verify specific values round-trip
    assert returned_item["title"] == item["title"]
    assert returned_item["company_name"] == item["company_name"]
    assert returned_item["source"] == item["source"]
    assert returned_item["source_job_id"] == item["source_job_id"]
    assert returned_item["url"] == item["url"]
    assert returned_item["apply_url"] == item["apply_url"]
    assert returned_item["ats_type"] == item["ats_type"]


async def test_search_filters_by_company_name(client):
    """GET /api/runs/{id}/items?q=... searches company_name across all item shapes."""
    items = [
        {**JOBSPY_ITEM, "index": 1, "company_name": "AlphaSearch Corp"},
        {**GREENHOUSE_ITEM, "index": 2, "company_name": "BetaSearch Inc"},
    ]
    run_id = _make_run("mixed", items)

    resp = await client.get(f"/api/runs/{run_id}/items?q=AlphaSearch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["company_name"] == "AlphaSearch Corp"


async def test_search_filters_by_source(client):
    """GET /api/runs/{id}/items?q=... searches source field."""
    items = [
        {**JOBSPY_ITEM, "index": 1, "source": "indeed"},
        {**GREENHOUSE_ITEM, "index": 2, "source": "greenhouse"},
    ]
    run_id = _make_run("mixed", items)

    resp = await client.get(f"/api/runs/{run_id}/items?q=greenhouse")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["source"] == "greenhouse"


async def test_backward_compat_old_company_field_searchable(client):
    """Pre-existing items_json with 'company' instead of 'company_name' are still searchable."""
    old_shape_item = {
        "index": 1,
        "outcome": "inserted",
        "job_id": str(uuid.uuid4()),
        "dedup_hash": "old001",
        "external_id": "old-ext-1",
        "title": "Legacy Engineer",
        "company": "OldFormat LLC",
        "location": "Boston",
        "apply_url": "https://example.com/old",
    }
    run_id = _make_run("greenhouse", [old_shape_item])

    resp = await client.get(f"/api/runs/{run_id}/items?q=OldFormat")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


async def test_outcome_filter_works(client):
    """GET /api/runs/{id}/items?outcome=inserted filters correctly."""
    items = [
        {**JOBSPY_ITEM, "index": 1, "outcome": "inserted"},
        {**GREENHOUSE_ITEM, "index": 2, "outcome": "duplicate"},
    ]
    run_id = _make_run("mixed", items)

    resp_inserted = await client.get(f"/api/runs/{run_id}/items?outcome=inserted")
    assert resp_inserted.status_code == 200
    assert resp_inserted.json()["total"] == 1
    assert resp_inserted.json()["items"][0]["outcome"] == "inserted"

    resp_dup = await client.get(f"/api/runs/{run_id}/items?outcome=duplicate")
    assert resp_dup.status_code == 200
    assert resp_dup.json()["total"] == 1
    assert resp_dup.json()["items"][0]["outcome"] == "duplicate"
