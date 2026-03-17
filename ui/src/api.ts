const BASE = "/api";

/** v1 API: Job list item (GET /api/jobs) */
export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  score: number;
  persona: string | null;
  pipeline_status: string;
  user_status: string;
  artifact_availability: boolean;
  source: string | null;
}

export interface JobsResponse {
  items: Job[];
  total: number;
  page: number;
  per_page: number;
}

/** v1 API: Job detail (GET /api/jobs/{id}) */
export interface JobDetail extends Omit<Job, "persona"> {
  description: string | null;
  url: string | null;
  apply_url: string | null;
  source: string | null;
  score_breakdown: { title_relevance?: number; seniority_fit?: number; tech_stack?: number; location_remote?: number; weights?: Record<string, number>; raw?: Record<string, unknown> } | null;
  ats_gaps: { missing_keywords: string[]; found_keywords?: string[]; ats_compatibility_score?: number; raw?: Record<string, unknown> } | null;
  persona: { matched_persona?: string; persona_confidence?: number; persona_rationale?: string } | null;
  artifacts: { id: string; kind: string; filename: string; persona_name: string | null; generation_status: string | null; created_at: string | null; download_url: string; preview_url: string }[];
  salary_min: number | null;
  salary_max: number | null;
  posted_at: string | null;
  remote_flag: boolean;
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

export async function updateJobStatus(id: string, status: string): Promise<{ id: string; user_status: string }> {
  const res = await fetch(`${BASE}/jobs/${id}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_status: status }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Status update failed: ${res.status}`);
  }
  return res.json();
}

export async function bulkUpdateStatus(jobIds: string[], status: string): Promise<{ updated: number }> {
  const res = await fetch(`${BASE}/jobs/bulk-status?status=${encodeURIComponent(status)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!res.ok) throw new Error(`Bulk status update failed: ${res.status}`);
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

export interface JobArtifact {
  id: string;
  kind: string;
  filename: string;
  persona_name: string | null;
  generation_status: string | null;
  created_at: string | null;
  download_url: string;
  preview_url: string;
}

export interface JobArtifactsResponse {
  items: JobArtifact[];
}

export async function fetchJobArtifacts(jobId: string): Promise<JobArtifactsResponse> {
  const res = await fetch(`${BASE}/jobs/${jobId}/artifacts`);
  if (!res.ok) throw new Error(`Failed to fetch artifacts: ${res.status}`);
  return res.json();
}

export async function triggerGenerateResume(jobId: string): Promise<{
  job_id: string;
  status: string;
  task_id?: string;
}> {
  const res = await fetch(`${BASE}/jobs/${jobId}/generate-resume`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Resume generation failed: ${res.status}`);
  }
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

/** Ready-to-apply feed: jobs with artifact ready, user_status=NEW */
export async function fetchReadyToApply(params?: {
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_dir?: string;
}): Promise<JobsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page != null) searchParams.set("page", String(params.page));
  if (params?.per_page != null) searchParams.set("per_page", String(params.per_page));
  if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params?.sort_dir) searchParams.set("sort_dir", params.sort_dir);
  const qs = searchParams.toString();
  const url = `${BASE}/jobs/ready-to-apply${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ready-to-apply: ${res.status}`);
  return res.json();
}

/** Ingest job from supported ATS URL (Greenhouse, Lever, Ashby) */
export async function ingestUrl(url: string): Promise<{
  run_id: string;
  status: string;
  task_id?: string;
  provider?: string;
}> {
  const res = await fetch(`${BASE}/jobs/ingest-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `URL ingest failed: ${res.status}`);
  }
  return res.json();
}

/** Trigger discovery run (AGG-1 or SERP1) */
export async function runDiscovery(body: {
  connector: "agg1" | "serp1";
  query?: string;
  location?: string;
  results_per_page?: number;
}): Promise<{ run_id: string; status: string; task_id?: string; connector?: string }> {
  const res = await fetch(`${BASE}/jobs/run-discovery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Discovery run failed: ${res.status}`);
  }
  return res.json();
}

/** Trigger canonical ingestion (Greenhouse, Lever, Ashby) */
export async function runIngestion(body: {
  connector: "greenhouse" | "lever" | "ashby";
  company_name: string;
  board_token?: string;
  client_name?: string;
  job_board_name?: string;
}): Promise<{ run_id: string; status: string; task_id?: string }> {
  const res = await fetch(`${BASE}/jobs/run-ingestion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Ingestion run failed: ${res.status}`);
  }
  return res.json();
}
