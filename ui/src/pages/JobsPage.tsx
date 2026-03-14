import { useCallback, useEffect, useState } from "react";
import {
  fetchJobs,
  approveJob,
  rejectJob,
  bulkApprove,
  bulkReject,
  type Job,
} from "../api";
import JobTable from "../components/JobTable";
import { notifyError } from "../notify";

const STATUSES = [
  "ALL",
  "NEW",
  "SCORED",
  "APPROVED",
  "REJECTED",
  "APPLIED",
  "APPLY_FAILED",
  "INTERVENTION_REQUIRED",
];

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(25);
  const [status, setStatus] = useState("ALL");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("score_total");
  const [sortDir, setSortDir] = useState("desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: String(perPage),
        sort_by: sortBy,
        sort_dir: sortDir,
      };
      if (status !== "ALL") params.status = status;
      if (search.trim()) params.q = search.trim();
      const data = await fetchJobs(params);
      setJobs(data.items);
      setTotal(data.total);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unknown error";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, status, search, sortBy, sortDir]);

  useEffect(() => {
    load();
  }, [load]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [status, search, sortBy, sortDir]);

  const handleAction = async (id: string, action: "approve" | "reject") => {
    try {
      if (action === "approve") await approveJob(id);
      else if (action === "reject") await rejectJob(id);
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

  const handleBulk = async (action: "approve" | "reject") => {
    if (selected.size === 0) return;
    try {
      const ids = Array.from(selected);
      if (action === "approve") await bulkApprove(ids);
      else await bulkReject(ids);
      setSelected(new Set());
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Bulk action failed";
      setError(message);
      notifyError(message);
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
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === "ALL" ? "All Statuses" : s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search title / company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm w-52"
          />
          <select
            value={sortBy}
            onChange={(e) => handleSort(e.target.value)}
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm"
          >
            <option value="score_total">Sort by Score</option>
            <option value="scraped_at">Sort by Scraped At</option>
            <option value="title">Sort by Title</option>
          </select>
          <button
            onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
            className="rounded border border-gray-300 bg-white px-2 py-1.5 text-sm"
            title="Toggle sort direction"
          >
            {sortDir === "desc" ? "↓" : "↑"}
          </button>
        </div>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 rounded bg-indigo-50 px-4 py-2 text-sm">
          <span className="font-medium">{selected.size} selected</span>
          <button
            onClick={() => handleBulk("approve")}
            className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
          >
            Bulk Approve
          </button>
          <button
            onClick={() => handleBulk("reject")}
            className="rounded bg-red-500 px-3 py-1 text-xs font-medium text-white hover:bg-red-600"
          >
            Bulk Reject
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-gray-500 hover:text-gray-700"
          >
            Clear
          </button>
        </div>
      )}

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
          <div className="h-4 w-5/6 animate-pulse rounded bg-gray-200" />
        </div>
      ) : (
        <JobTable
          jobs={jobs}
          selected={selected}
          onToggle={handleToggle}
          onToggleAll={handleToggleAll}
          onAction={handleAction}
        />
      )}

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          {total} job{total !== 1 ? "s" : ""} total
        </span>
        <div className="flex items-center gap-2">
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
