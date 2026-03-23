import test from "node:test";
import assert from "node:assert/strict";

import { buildRunItemDisplay } from "./runItemDisplay.js";

test("canonical run items expose non-blank display fields", () => {
  const display = buildRunItemDisplay({
    index: 1,
    outcome: "inserted",
    job_id: "job-1",
    dedup_hash: "abc",
    source: "greenhouse",
    source_job_id: "gh-1",
    title: "Backend Engineer",
    company_name: "Acme Corp",
    location: "Remote",
    url: "https://boards.greenhouse.io/acme/jobs/1",
    apply_url: "https://boards.greenhouse.io/acme/jobs/1#app",
    ats_type: "greenhouse",
    raw_payload_json: { id: 1 },
  });

  assert.equal(display.companyName, "Acme Corp");
  assert.equal(display.location, "Remote");
  assert.equal(display.source, "greenhouse");
  assert.equal(display.sourceJobId, "gh-1");
  assert.equal(display.listingHref, "https://boards.greenhouse.io/acme/jobs/1");
  assert.equal(display.applyHref, "https://boards.greenhouse.io/acme/jobs/1#app");
});

test("discovery run items no longer render blank company or listing fields", () => {
  const display = buildRunItemDisplay({
    index: 1,
    outcome: "inserted",
    job_id: "job-2",
    dedup_hash: "def",
    source: "agg1",
    source_job_id: "adz-2",
    title: "Data Scientist",
    company_name: "DataCo",
    location: "New York, NY",
    url: "https://adzuna.example/jobs/2",
    apply_url: "https://adzuna.example/apply/2",
    ats_type: "agg1",
    raw_payload_json: { provider: "agg1" },
  });

  assert.equal(display.companyName, "DataCo");
  assert.equal(display.source, "agg1");
  assert.equal(display.sourceJobId, "adz-2");
  assert.equal(display.listingHref, "https://adzuna.example/jobs/2");
  assert.equal(display.applyHref, "https://adzuna.example/apply/2");
});
