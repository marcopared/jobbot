"""Contract tests for ingestion endpoint response shapes.

These tests verify that the API response contracts consumed by the UI
(ui/src/api.ts types) remain stable. They fail loudly if required fields
disappear or change type.

Does not require Celery workers — only verifies HTTP response shapes.

Surfaces covered:
  POST /api/jobs/run-ingestion
  POST /api/jobs/ingest-url
  POST /api/jobs/manual-ingest
  GET  /api/runs/{id}
  GET  /api/runs/{id}/items
"""

import uuid

import httpx
import pytest
from httpx import ASGITransport

from apps.api.main import app
from core.db.models import ScrapeRun, ScrapeRunStatus
from core.db.session import get_sync_session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_run_with_items(source: str, items: list[dict]) -> str:
    """Insert a ScrapeRun with items_json. Returns run_id as str."""
    inserted = sum(1 for i in items if i.get("outcome") == "inserted")
    duplicates = sum(1 for i in items if i.get("outcome") == "duplicate")
    with get_sync_session() as session:
        run = ScrapeRun(
            source=source,
            status=ScrapeRunStatus.SUCCESS.value,
            stats_json={
                "fetched": len(items),
                "inserted": inserted,
                "duplicates": duplicates,
                "errors": 0,
            },
            items_json=items,
        )
        session.add(run)
        session.commit()
        return str(run.id)


# ---------------------------------------------------------------------------
# Field sets — derived from ui/src/api.ts interfaces
# ---------------------------------------------------------------------------

# POST /api/jobs/run-ingestion → { run_id, status, task_id }
RUN_INGESTION_REQUIRED = {"run_id", "status", "task_id"}

# POST /api/jobs/ingest-url → { run_id, status, task_id, provider }
INGEST_URL_REQUIRED = {"run_id", "status", "task_id", "provider"}

# POST /api/jobs/manual-ingest → ManualIngestResponse { run_id, job_id, status }
MANUAL_INGEST_REQUIRED = {"run_id", "job_id", "status"}

# GET /api/runs/{id} → Run interface
RUN_DETAIL_REQUIRED = {"id", "source", "status", "item_counts", "created_at"}

# GET /api/runs/{id}/items → RunItemsResponse envelope
RUN_ITEMS_ENVELOPE_REQUIRED = {"items", "total", "page", "per_page", "counts"}
RUN_ITEMS_COUNTS_REQUIRED = {"all", "inserted", "duplicates"}

# RunItem interface — every item returned by /api/runs/{id}/items
UI_RUN_ITEM_REQUIRED = {
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


# ===========================================================================
# 1. POST /api/jobs/run-ingestion — response contract
# ===========================================================================


@pytest.mark.parametrize(
    "connector,extra",
    [
        ("greenhouse", {"board_token": "contract-gh", "company_name": "ContractGH"}),
        ("lever", {"client_name": "contract-lv", "company_name": "ContractLV"}),
        ("ashby", {"job_board_name": "contract-ash", "company_name": "ContractAsh"}),
    ],
)
async def test_run_ingestion_response_shape(client, connector, extra):
    """run-ingestion response includes every field the UI consumes."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={"connector": connector, **extra},
    )
    assert resp.status_code == 200
    data = resp.json()

    missing = RUN_INGESTION_REQUIRED - set(data.keys())
    assert not missing, f"run-ingestion missing fields: {missing}"

    assert isinstance(data["run_id"], str) and len(data["run_id"]) > 0
    assert isinstance(data["task_id"], str)
    assert data["status"] == "RUNNING"
    # run_id must be a valid UUID
    uuid.UUID(data["run_id"])


# ===========================================================================
# 2. POST /api/jobs/ingest-url — response contract
# ===========================================================================


@pytest.mark.parametrize(
    "url,expected_provider",
    [
        ("https://boards.greenhouse.io/contractco/jobs/12345", "greenhouse"),
        ("https://jobs.lever.co/contractco/aaaa-bbbb-cccc", "lever"),
        ("https://jobs.ashbyhq.com/contractco/aaaa-bbbb-cccc", "ashby"),
    ],
)
async def test_ingest_url_response_shape(client, monkeypatch, url, expected_provider):
    """ingest-url response includes every field the UI consumes."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "url_ingest_enabled", True)

    resp = await client.post("/api/jobs/ingest-url", json={"url": url})
    assert resp.status_code == 200
    data = resp.json()

    missing = INGEST_URL_REQUIRED - set(data.keys())
    assert not missing, f"ingest-url missing fields: {missing}"

    assert isinstance(data["run_id"], str) and len(data["run_id"]) > 0
    assert isinstance(data["provider"], str)
    assert data["provider"] == expected_provider
    assert isinstance(data["task_id"], str)
    uuid.UUID(data["run_id"])


# ===========================================================================
# 3. POST /api/jobs/manual-ingest — response contract
# ===========================================================================


async def test_manual_ingest_success_response_shape(client):
    """manual-ingest SUCCESS response has all fields the UI consumes."""
    unique = str(uuid.uuid4())[:8]
    resp = await client.post(
        "/api/jobs/manual-ingest",
        json={
            "title": f"Contract Success {unique}",
            "company": "ContractCo",
            "location": "Remote",
            "apply_url": f"https://example.com/contract-ok-{unique}",
            "description": "Contract test.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    missing = MANUAL_INGEST_REQUIRED - set(data.keys())
    assert not missing, f"manual-ingest SUCCESS missing fields: {missing}"

    assert data["status"] == "SUCCESS"
    assert isinstance(data["run_id"], str) and len(data["run_id"]) > 0
    assert isinstance(data["job_id"], str) and len(data["job_id"]) > 0
    assert "task_id" in data
    uuid.UUID(data["run_id"])
    uuid.UUID(data["job_id"])


async def test_manual_ingest_duplicate_response_shape(client):
    """manual-ingest DUPLICATE response preserves the same contract shape."""
    unique = str(uuid.uuid4())[:8]
    payload = {
        "title": f"Contract Dup {unique}",
        "company": "DupContractCo",
        "location": "Remote",
        "apply_url": f"https://example.com/contract-dup-{unique}",
        "description": "Dup contract test.",
    }
    resp1 = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "SUCCESS"

    resp2 = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp2.status_code == 200
    data = resp2.json()

    missing = MANUAL_INGEST_REQUIRED - set(data.keys())
    assert not missing, f"manual-ingest DUPLICATE missing fields: {missing}"

    assert data["status"] == "DUPLICATE"
    assert data["job_id"] is None
    assert isinstance(data["run_id"], str)
    uuid.UUID(data["run_id"])


# ===========================================================================
# 4. GET /api/runs/{id} — run detail response contract
# ===========================================================================


async def test_run_detail_response_shape(client):
    """GET /api/runs/{id} response has every field the UI Run interface expects."""
    run_id = _insert_run_with_items("greenhouse", [])
    resp = await client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    missing = RUN_DETAIL_REQUIRED - set(data.keys())
    assert not missing, f"run detail missing fields: {missing}"

    assert isinstance(data["id"], str)
    assert isinstance(data["source"], str)
    assert isinstance(data["status"], str)
    assert isinstance(data["item_counts"], dict)
    for k in ("all", "inserted", "duplicates"):
        assert k in data["item_counts"], f"item_counts missing '{k}'"
        assert isinstance(data["item_counts"][k], int)


# ===========================================================================
# 5. GET /api/runs/{id}/items — envelope contract
# ===========================================================================


async def test_run_items_envelope_shape(client):
    """GET /api/runs/{id}/items envelope matches RunItemsResponse interface."""
    run_id = _insert_run_with_items("greenhouse", [
        {
            "index": 1,
            "outcome": "inserted",
            "job_id": str(uuid.uuid4()),
            "dedup_hash": "envelope-hash",
            "source": "greenhouse",
            "source_job_id": "gh-env-1",
            "title": "Envelope Test",
            "company_name": "EnvelopeCo",
            "location": "SF",
            "url": "https://boards.greenhouse.io/co/jobs/1",
            "apply_url": "https://boards.greenhouse.io/co/jobs/1#app",
            "ats_type": "greenhouse",
            "raw_payload_json": {"test": True},
        },
    ])

    resp = await client.get(f"/api/runs/{run_id}/items")
    assert resp.status_code == 200
    data = resp.json()

    missing = RUN_ITEMS_ENVELOPE_REQUIRED - set(data.keys())
    assert not missing, f"run items envelope missing fields: {missing}"

    assert isinstance(data["items"], list) and len(data["items"]) == 1
    assert isinstance(data["total"], int) and data["total"] == 1
    assert isinstance(data["page"], int)
    assert isinstance(data["per_page"], int)
    assert isinstance(data["counts"], dict)

    missing_counts = RUN_ITEMS_COUNTS_REQUIRED - set(data["counts"].keys())
    assert not missing_counts, f"counts sub-object missing fields: {missing_counts}"


# ===========================================================================
# 6. RunItem schema contract per source — matches ui/src/api.ts RunItem
# ===========================================================================


@pytest.mark.parametrize(
    "label,source,item",
    [
        (
            "greenhouse",
            "greenhouse",
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "ctr-gh",
                "source": "greenhouse",
                "source_job_id": "gh-c1",
                "title": "GH Engineer",
                "company_name": "GreenCo",
                "location": "NYC",
                "url": "https://boards.greenhouse.io/co/jobs/1",
                "apply_url": "https://boards.greenhouse.io/co/jobs/1#app",
                "ats_type": "greenhouse",
                "raw_payload_json": {"id": 1},
            },
        ),
        (
            "lever",
            "lever",
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "ctr-lv",
                "source": "lever",
                "source_job_id": "lv-c1",
                "title": "LV Designer",
                "company_name": "LeverCo",
                "location": "Remote",
                "url": "https://jobs.lever.co/co/1",
                "apply_url": "https://jobs.lever.co/co/1/apply",
                "ats_type": "lever",
                "raw_payload_json": {"id": "lv-c1"},
            },
        ),
        (
            "ashby",
            "ashby",
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "ctr-ash",
                "source": "ashby",
                "source_job_id": "ash-c1",
                "title": "Ashby PM",
                "company_name": "AshbyCo",
                "location": "LA",
                "url": "https://jobs.ashbyhq.com/co/1",
                "apply_url": "https://jobs.ashbyhq.com/co/1/application",
                "ats_type": "ashby",
                "raw_payload_json": {"id": "ash-c1"},
            },
        ),
        (
            "agg1_discovery",
            "agg1",
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "ctr-agg1",
                "source": "agg1",
                "source_job_id": "adz-c1",
                "title": "Discovery Eng",
                "company_name": "AdzCo",
                "location": "Austin",
                "url": "https://adzuna.com/job/1",
                "apply_url": "https://adzuna.com/apply/1",
                "ats_type": "agg1",
                "raw_payload_json": {"category": "engineering"},
            },
        ),
        (
            "manual_intake",
            "manual_intake",
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "ctr-manual",
                "source": "manual_intake",
                "source_job_id": None,
                "title": "Manual Job",
                "company_name": "ManualCo",
                "location": "Denver",
                "url": "https://example.com/manual",
                "apply_url": "https://example.com/apply",
                "ats_type": "manual_intake",
                "raw_payload_json": None,
            },
        ),
        (
            "url_ingest",
            "url_ingest",
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "ctr-url",
                "source": "url_ingest",
                "source_job_id": "url-c1",
                "title": "URL Ingest Eng",
                "company_name": "URLCo",
                "location": "SF",
                "url": "https://boards.greenhouse.io/urlco/jobs/1",
                "apply_url": "https://boards.greenhouse.io/urlco/jobs/1#app",
                "ats_type": "greenhouse",
                "raw_payload_json": {"via": "url_ingest"},
            },
        ),
    ],
)
async def test_run_item_matches_ui_interface(client, label, source, item):
    """Each source's run items include every field from the UI RunItem interface."""
    run_id = _insert_run_with_items(source, [item])
    resp = await client.get(f"/api/runs/{run_id}/items")
    assert resp.status_code == 200

    returned = resp.json()["items"][0]
    missing = UI_RUN_ITEM_REQUIRED - set(returned.keys())
    assert not missing, (
        f"[{label}] RunItem contract violated — missing: {missing}"
    )

    # Values round-trip correctly
    assert returned["company_name"] == item["company_name"]
    assert returned["source"] == item["source"]
    assert returned["url"] == item["url"]
    assert returned["apply_url"] == item["apply_url"]
    assert returned["raw_payload_json"] == item["raw_payload_json"]


# ===========================================================================
# 7. Critical fields — fail loudly if any of these disappear
# ===========================================================================


class TestCriticalFieldPresence:
    """Guard-rail tests that fail with explicit messages when critical fields
    are removed from any ingestion response surface."""

    async def test_run_ingestion_has_run_id(self, client):
        resp = await client.post(
            "/api/jobs/run-ingestion",
            json={"connector": "greenhouse", "board_token": "x", "company_name": "X"},
        )
        assert resp.status_code == 200
        assert "run_id" in resp.json(), (
            "CRITICAL: 'run_id' missing from run-ingestion — UI navigation will break"
        )

    async def test_ingest_url_has_run_id_and_provider(self, client, monkeypatch):
        from apps.api.routes import jobs as jobs_route

        monkeypatch.setattr(jobs_route.settings, "url_ingest_enabled", True)
        resp = await client.post(
            "/api/jobs/ingest-url",
            json={"url": "https://boards.greenhouse.io/x/jobs/1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data, "CRITICAL: 'run_id' missing from ingest-url"
        assert "provider" in data, "CRITICAL: 'provider' missing from ingest-url"

    async def test_manual_ingest_has_run_id_and_status(self, client):
        unique = str(uuid.uuid4())[:8]
        resp = await client.post(
            "/api/jobs/manual-ingest",
            json={
                "title": f"Crit {unique}",
                "company": "CritCo",
                "location": "Remote",
                "apply_url": f"https://example.com/crit-{unique}",
                "description": "Critical field guard.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data, "CRITICAL: 'run_id' missing from manual-ingest"
        assert "job_id" in data, "CRITICAL: 'job_id' missing from manual-ingest"
        assert "status" in data, "CRITICAL: 'status' missing from manual-ingest"

    async def test_run_items_have_company_name(self, client):
        """company_name must not revert to the old 'company' key."""
        run_id = _insert_run_with_items("greenhouse", [
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "crit-cn",
                "source": "greenhouse",
                "source_job_id": "crit-1",
                "title": "Crit Test",
                "company_name": "CritCo",
                "location": "Remote",
                "url": "https://example.com/crit",
                "apply_url": "https://example.com/crit-apply",
                "ats_type": "greenhouse",
                "raw_payload_json": None,
            },
        ])
        resp = await client.get(f"/api/runs/{run_id}/items")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "company_name" in item, (
            "CRITICAL: 'company_name' missing from run item — "
            "UI RunDetailPage.tsx expects this field"
        )

    async def test_run_items_have_apply_url(self, client):
        run_id = _insert_run_with_items("greenhouse", [
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "crit-au",
                "source": "greenhouse",
                "source_job_id": "crit-2",
                "title": "Apply URL Test",
                "company_name": "ApplyCo",
                "location": "Remote",
                "url": "https://example.com/j",
                "apply_url": "https://example.com/apply",
                "ats_type": "greenhouse",
                "raw_payload_json": None,
            },
        ])
        resp = await client.get(f"/api/runs/{run_id}/items")
        item = resp.json()["items"][0]
        assert "apply_url" in item, "CRITICAL: 'apply_url' missing from run item"

    async def test_run_items_have_source_and_url(self, client):
        run_id = _insert_run_with_items("greenhouse", [
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "crit-su",
                "source": "greenhouse",
                "source_job_id": "crit-3",
                "title": "Source URL Test",
                "company_name": "SourceCo",
                "location": "Remote",
                "url": "https://example.com/src",
                "apply_url": "https://example.com/apply",
                "ats_type": "greenhouse",
                "raw_payload_json": None,
            },
        ])
        resp = await client.get(f"/api/runs/{run_id}/items")
        item = resp.json()["items"][0]
        assert "source" in item, "CRITICAL: 'source' missing from run item"
        assert "url" in item, "CRITICAL: 'url' missing from run item"

    async def test_run_items_have_raw_payload_json(self, client):
        run_id = _insert_run_with_items("greenhouse", [
            {
                "index": 1,
                "outcome": "inserted",
                "job_id": str(uuid.uuid4()),
                "dedup_hash": "crit-rp",
                "source": "greenhouse",
                "source_job_id": "crit-4",
                "title": "Raw Payload Test",
                "company_name": "PayloadCo",
                "location": "Remote",
                "url": "https://example.com/rp",
                "apply_url": "https://example.com/rp-apply",
                "ats_type": "greenhouse",
                "raw_payload_json": {"preserved": True},
            },
        ])
        resp = await client.get(f"/api/runs/{run_id}/items")
        item = resp.json()["items"][0]
        assert "raw_payload_json" in item, (
            "CRITICAL: 'raw_payload_json' missing from run item"
        )

    async def test_run_detail_has_item_counts(self, client):
        run_id = _insert_run_with_items("greenhouse", [])
        resp = await client.get(f"/api/runs/{run_id}")
        data = resp.json()
        assert "item_counts" in data, (
            "CRITICAL: 'item_counts' missing from run detail"
        )


# ===========================================================================
# 8. End-to-end roundtrip: manual-ingest → /runs/{id}/items
# ===========================================================================


async def test_manual_ingest_items_roundtrip(client):
    """A manual-ingest job appears in /runs/{id}/items with the full RunItem contract."""
    unique = str(uuid.uuid4())[:8]
    ingest_resp = await client.post(
        "/api/jobs/manual-ingest",
        json={
            "title": f"Roundtrip {unique}",
            "company": "RoundtripCo",
            "location": "Portland, OR",
            "apply_url": f"https://example.com/rt-{unique}",
            "description": "Roundtrip contract test.",
        },
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["status"] == "SUCCESS"
    run_id = ingest_resp.json()["run_id"]

    items_resp = await client.get(f"/api/runs/{run_id}/items")
    assert items_resp.status_code == 200
    items_data = items_resp.json()

    assert items_data["counts"]["inserted"] == 1
    assert len(items_data["items"]) == 1

    item = items_data["items"][0]
    missing = UI_RUN_ITEM_REQUIRED - set(item.keys())
    assert not missing, f"Manual ingest roundtrip — missing RunItem fields: {missing}"

    # Verify values written by manual-ingest match what the UI reads back
    assert item["company_name"] == "RoundtripCo"
    assert item["source"] == "manual_intake"
    assert item["ats_type"] == "manual_intake"
    assert f"rt-{unique}" in item["apply_url"]
