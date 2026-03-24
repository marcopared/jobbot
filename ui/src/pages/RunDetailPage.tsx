import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchRun, fetchRunItems, type Run, type RunItem } from "../api";
import { notifyError } from "../notify";
import { buildRunItemDisplay } from "./runItemDisplay";

type OutcomeFilter = "all" | "inserted" | "duplicate";

function formatDate(value: string | null): string {
  if (!value) return "N/A";
  return new Date(value).toLocaleString();
}

function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt) return "N/A";
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  return `${seconds}s`;
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [items, setItems] = useState<RunItem[]>([]);
  const [counts, setCounts] = useState({ all: 0, inserted: 0, duplicates: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<OutcomeFilter>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [perPage] = useState(100);
  const [total, setTotal] = useState(0);

  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / perPage)), [total, perPage]);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: String(perPage),
      };
      if (outcome !== "all") params.outcome = outcome;
      if (query.trim()) params.q = query.trim();
      const [runData, itemsData] = await Promise.all([fetchRun(id), fetchRunItems(id, params)]);
      setRun(runData);
      setItems(itemsData.items);
      setTotal(itemsData.total);
      setCounts(itemsData.counts);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load run details";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [id, outcome, page, perPage, query]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [outcome, query]);

  if (!id) return <div className="text-sm text-gray-500">Missing run id.</div>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Scrape Run Details</h1>
          <p className="text-sm text-gray-600">
            Run ID: <span className="font-mono text-xs">{id}</span>
          </p>
        </div>
        <Link to="/runs" className="text-sm text-indigo-700 underline">
          Back to runs
        </Link>
      </div>

      {run && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="text-gray-500">Status</div>
              <div className="mt-1 font-medium">{run.status}</div>
            </div>
            <div>
              <div className="text-gray-500">Started</div>
              <div className="mt-1 font-medium">{formatDate(run.started_at)}</div>
            </div>
            <div>
              <div className="text-gray-500">Finished</div>
              <div className="mt-1 font-medium">{formatDate(run.finished_at)}</div>
            </div>
            <div>
              <div className="text-gray-500">Duration</div>
              <div className="mt-1 font-medium">{formatDuration(run.started_at, run.finished_at)}</div>
            </div>
          </div>
          <div className="mt-3 text-sm text-gray-700">
            fetched {counts.all} · inserted {counts.inserted} · duplicates {counts.duplicates}
          </div>
        </section>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setOutcome("all")}
            className={`rounded px-3 py-1.5 text-sm ${
              outcome === "all" ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-700"
            }`}
          >
            All ({counts.all})
          </button>
          <button
            onClick={() => setOutcome("inserted")}
            className={`rounded px-3 py-1.5 text-sm ${
              outcome === "inserted" ? "bg-green-700 text-white" : "bg-green-100 text-green-800"
            }`}
          >
            Inserted ({counts.inserted})
          </button>
          <button
            onClick={() => setOutcome("duplicate")}
            className={`rounded px-3 py-1.5 text-sm ${
              outcome === "duplicate" ? "bg-amber-700 text-white" : "bg-amber-100 text-amber-800"
            }`}
          >
            Duplicates ({counts.duplicates})
          </button>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title/company/source"
            className="ml-auto w-full rounded border border-gray-300 px-3 py-1.5 text-sm md:w-72"
          />
        </div>
      </section>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-2 rounded border border-gray-200 bg-white p-6">
          <div className="h-4 w-1/3 animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-gray-200" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">#</th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">Outcome</th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">Title / Company</th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">URLs</th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">Refs</th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => {
                const display = buildRunItemDisplay(item);
                return (
                  <tr key={`${item.index}-${item.dedup_hash}`}>
                  <td className="px-3 py-2 text-gray-700">{item.index}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        item.outcome === "inserted"
                          ? "bg-green-100 text-green-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {item.outcome}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-900">{item.title}</div>
                    <div className="text-gray-600">{display.companyName}</div>
                    <div className="text-xs text-gray-500">{display.location}</div>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {display.listingHref ? (
                      <div>
                        <a
                          href={display.listingHref}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-700 underline"
                        >
                          listing
                        </a>
                      </div>
                    ) : (
                      <div className="text-gray-400">listing unavailable</div>
                    )}
                    {display.applyHref && (
                      <div>
                        <a
                          href={display.applyHref}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-700 underline"
                        >
                          apply
                        </a>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-600">
                    <div>source: {display.source}</div>
                    <div>source id: {display.sourceJobId}</div>
                    <div>job id: {display.jobId}</div>
                  </td>
                  <td className="px-3 py-2">
                    <details>
                      <summary className="cursor-pointer text-xs text-indigo-700 underline">
                        View JSON
                      </summary>
                      <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-2 text-xs text-gray-100">
                        {display.rawPayloadText}
                      </pre>
                    </details>
                  </td>
                  </tr>
                );
              })}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-gray-400">
                    No listings for this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-gray-600">
          Page {page} / {maxPage}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(maxPage, p + 1))}
          disabled={page >= maxPage}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
