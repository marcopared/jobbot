const BASE = "/api";

export interface Job {
  id: string;
  title: string;
  company_name_raw: string;
  source: string;
  status: string;
  score_total: number;
  ats_match_score: number;
  location: string | null;
  url: string;
  apply_url: string | null;
  ats_type: string;
  remote_flag: boolean;
  scraped_at: string | null;
}

export interface JobsResponse {
  items: Job[];
  total: number;
  page: number;
  per_page: number;
}

export interface JobDetail extends Job {
  description: string | null;
  salary_min: number | null;
  salary_max: number | null;
  posted_at: string | null;
  score_breakdown_json: Record<string, number> | null;
  ats_match_breakdown_json: Record<string, unknown> | null;
  source_job_id: string | null;
  source_payload_json: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Run {
  id: string;
  source: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  params_json: Record<string, unknown> | null;
  stats_json: Record<string, number> | null;
  item_counts:
    | {
        all: number;
        inserted: number;
        duplicates: number;
      }
    | null;
  error_text: string | null;
  created_at: string | null;
}

export interface RunsResponse {
  items: Run[];
  total: number;
  page: number;
  per_page: number;
}

export interface RunItem {
  index: number;
  outcome: "inserted" | "duplicate";
  job_id: string | null;
  dedup_hash: string;
  source: string;
  source_job_id: string | null;
  title: string;
  company_name: string;
  location: string | null;
  url: string;
  apply_url: string | null;
  ats_type: string;
  backfilled_payload?: boolean;
  raw_payload_json: Record<string, unknown> | null;
}

export interface RunItemsResponse {
  items: RunItem[];
  total: number;
  page: number;
  per_page: number;
  counts: {
    all: number;
    inserted: number;
    duplicates: number;
  };
}

export async function fetchJobs(params: Record<string, string>): Promise<JobsResponse> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/jobs?${qs}`);
  if (!res.ok) throw new Error(`Failed to fetch jobs: ${res.status}`);
  return res.json();
}

export async function fetchJob(id: string): Promise<JobDetail> {
  const res = await fetch(`${BASE}/jobs/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch job: ${res.status}`);
  return res.json();
}

export async function approveJob(id: string): Promise<{ id: string; status: string }> {
  const res = await fetch(`${BASE}/jobs/${id}/approve`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Approve failed: ${res.status}`);
  }
  return res.json();
}

export async function rejectJob(id: string): Promise<{ id: string; status: string }> {
  const res = await fetch(`${BASE}/jobs/${id}/reject`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Reject failed: ${res.status}`);
  }
  return res.json();
}

export async function bulkApprove(jobIds: string[]): Promise<{ updated: number }> {
  const res = await fetch(`${BASE}/jobs/bulk-approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!res.ok) throw new Error(`Bulk approve failed: ${res.status}`);
  return res.json();
}

export async function bulkReject(jobIds: string[]): Promise<{ updated: number }> {
  const res = await fetch(`${BASE}/jobs/bulk-reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!res.ok) throw new Error(`Bulk reject failed: ${res.status}`);
  return res.json();
}

export async function fetchRuns(params: Record<string, string>): Promise<RunsResponse> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/runs?${qs}`);
  if (!res.ok) throw new Error(`Failed to fetch runs: ${res.status}`);
  return res.json();
}

export async function fetchRun(id: string): Promise<Run> {
  const res = await fetch(`${BASE}/runs/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch run: ${res.status}`);
  return res.json();
}

export async function fetchRunItems(
  runId: string,
  params: Record<string, string>,
): Promise<RunItemsResponse> {
  const qs = new URLSearchParams(params).toString();
  const suffix = qs ? `?${qs}` : "";
  const res = await fetch(`${BASE}/runs/${runId}/items${suffix}`);
  if (!res.ok) throw new Error(`Failed to fetch run items: ${res.status}`);
  return res.json();
}

export async function runScrapeNow(body?: {
  query?: string;
  location?: string;
  hours_old?: number;
  results_wanted?: number;
}): Promise<{ run_id: string; status: string; task_id?: string }> {
  const res = await fetch(`${BASE}/jobs/run-scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Run scrape failed: ${res.status}`);
  }
  return res.json();
}
