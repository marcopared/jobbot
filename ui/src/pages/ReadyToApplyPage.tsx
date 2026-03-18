import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchReadyToApply,
  ingestUrl,
  updateJobStatus,
  bulkUpdateStatus,
  type Job,
} from "../api";
import JobTable from "../components/JobTable";
import EmptyState from "../components/EmptyState";
import { notifyError } from "../notify";

export default function ReadyToApplyPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(25);
  const [sortBy, setSortBy] = useState("artifact_ready_at");
  const [sortDir, setSortDir] = useState("desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [urlInput, setUrlInput] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<{ runId: string } | null>(
    null,
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReadyToApply({
        page,
        per_page: perPage,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setJobs(data.items);
      setTotal(data.total);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sortBy, sortDir]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [sortBy, sortDir]);

  const handleAction = async (id: string, status: string) => {
    try {
      await updateJobStatus(id, status);
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Action failed";
      setError(message);
      notifyError(message);
    }
  };

  const handleToggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleToggleAll = () => {
    if (jobs.every((j) => selected.has(j.id))) {
      setSelected(new Set());
    } else {
      setSelected(new Set(jobs.map((j) => j.id)));
    }
  };

  const handleBulk = async (status: string) => {
    if (selected.size === 0) return;
    try {
      const ids = Array.from(selected);
      await bulkUpdateStatus(ids, status);
      setSelected(new Set());
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Bulk action failed";
      setError(message);
      notifyError(message);
    }
  };

  const handleIngestUrl = async () => {
    const url = urlInput.trim();
    if (!url) return;
    setIngesting(true);
    setIngestResult(null);
    setError(null);
    try {
      const data = await ingestUrl(url);
      setIngestResult({ runId: data.run_id });
      setUrlInput("");
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "URL ingest failed";
      setError(message);
      notifyError(message);
    } finally {
      setIngesting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border-2 border-indigo-100 bg-indigo-50/50 px-5 py-6">
        <h1 className="text-2xl font-bold text-gray-900">Ready to Apply</h1>
        <p className="mt-1 text-sm text-gray-700">
          Your operational home — jobs with tailored resumes ready. Download the
          resume, open the application link, and apply <strong>manually</strong>
          . JobBot never auto-submits.
        </p>
        <div className="mt-3 rounded border border-indigo-200 bg-white px-3 py-2 text-xs text-indigo-900">
          Operator flow: <strong>1)</strong> click <strong>Apply</strong> in the
          table to open Job Detail, <strong>2)</strong> download artifact,{" "}
          <strong>3)</strong> open external apply link, <strong>4)</strong> mark
          applied.
        </div>

        {/* URL Ingest form */}
        <div className="mt-6 rounded-lg border border-indigo-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            Paste job URL
          </h2>
          <p className="mb-3 text-xs text-gray-500">
            Supported ATS: Greenhouse, Lever, Ashby. Paste a job URL to add it
            to the pipeline.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              type="url"
              placeholder="https://boards.greenhouse.io/company/jobs/123..."
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              className="min-w-0 flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              onClick={() => void handleIngestUrl()}
              disabled={ingesting || !urlInput.trim()}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {ingesting ? "Ingesting…" : "Ingest URL"}
            </button>
          </div>
          {ingestResult && (
            <p className="mt-2 text-sm text-green-700">
              Ingest started.{" "}
              <Link
                to={`/runs/${ingestResult.runId}`}
                className="font-medium underline"
              >
                View run
              </Link>
            </p>
          )}
          <div className="mt-3 border-t border-gray-100 pt-3">
            <Link
              to="/jobs/manual-intake"
              className="inline-flex items-center rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 no-underline"
            >
              Or paste full description
            </Link>
            <p className="mt-1 text-xs text-gray-500">
              Use this when there is no supported ATS URL and you want to enter
              extracted fields manually.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-bold">
            ×
          </button>
        </div>
      )}

      {loading ? (
        <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-4">
          <div className="h-4 w-1/3 animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          title="No jobs ready yet"
          description="Run discovery (AGG-1/SERP1) or canonical ingestion from Runs, or paste a supported ATS URL above. Once jobs pass ATS and generation gate, resumes appear here."
          action={
            <div className="flex flex-wrap gap-3 justify-center">
              <Link
                to="/runs"
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 no-underline"
              >
                Go to Runs
              </Link>
              <Link
                to="/jobs"
                className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 no-underline"
              >
                View All Jobs
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="rounded border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600">
            Apply column opens Job Detail where <strong>Download Resume</strong>{" "}
            and <strong>Open Application</strong> are shown together for manual
            submission.
          </div>
          <JobTable
            jobs={jobs}
            selected={selected}
            onToggle={handleToggle}
            onToggleAll={handleToggleAll}
            onAction={handleAction}
            showApplyLink
          />
        </>
      )}

      {selected.size > 0 && (
        <div className="flex items-center gap-2 rounded bg-indigo-50 px-4 py-2 text-sm">
          <span className="font-medium">{selected.size} selected</span>
          <button
            onClick={() => void handleBulk("SAVED")}
            className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
          >
            Bulk Save
          </button>
          <button
            onClick={() => void handleBulk("ARCHIVED")}
            className="rounded bg-red-500 px-3 py-1 text-xs font-medium text-white hover:bg-red-600"
          >
            Bulk Archive
          </button>
          <button
            onClick={() => void handleBulk("APPLIED")}
            className="rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700"
          >
            Mark Applied
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-gray-500 hover:text-gray-700"
          >
            Clear
          </button>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          {total} job{total !== 1 ? "s" : ""} ready
        </span>
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => handleSort(e.target.value)}
            className="rounded border border-gray-300 bg-white px-2 py-1 text-sm"
          >
            <option value="artifact_ready_at">Sort by Ready</option>
            <option value="score_total">Sort by Score</option>
            <option value="scraped_at">Sort by Scraped</option>
          </select>
          <button
            onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
            className="rounded border px-2 py-1"
          >
            {sortDir === "desc" ? "↓" : "↑"}
          </button>
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
