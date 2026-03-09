import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchRuns, runScrapeNow, type Run } from "../api";
import { notifyError } from "../notify";

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

function statsText(run: Run): string {
  const s = run.stats_json ?? {};
  const fetched = typeof s.fetched === "number" ? s.fetched : 0;
  const inserted = typeof s.inserted === "number" ? s.inserted : 0;
  const duplicates = typeof s.duplicates === "number" ? s.duplicates : 0;
  return `fetched ${fetched} · inserted ${inserted} · duplicates ${duplicates}`;
}

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasRunning = useMemo(() => runs.some((r) => r.status === "RUNNING"), [runs]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRuns({ page: "1", per_page: "25" });
      setRuns(data.items);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load runs";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!hasRunning) return;
    const id = window.setInterval(() => {
      void load();
    }, 2000);
    return () => window.clearInterval(id);
  }, [hasRunning, load]);

  const onRunScrape = async () => {
    setTriggering(true);
    setError(null);
    try {
      await runScrapeNow();
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to trigger scrape";
      setError(message);
      notifyError(message);
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Scrape Runs</h1>
        <button
          onClick={() => void onRunScrape()}
          disabled={triggering}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {triggering ? "Triggering..." : "Run Scrape Now"}
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-2 rounded border border-gray-200 bg-white p-6">
          <div className="h-4 w-1/3 animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-4/5 animate-pulse rounded bg-gray-200" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Source</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Status</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Started</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Duration</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Stats</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="px-3 py-2">{run.source}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        run.status === "RUNNING"
                          ? "bg-yellow-100 text-yellow-800"
                          : run.status === "SUCCESS"
                            ? "bg-green-100 text-green-800"
                            : "bg-red-100 text-red-800"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">{formatDate(run.started_at)}</td>
                  <td className="px-3 py-2">{formatDuration(run.started_at, run.finished_at)}</td>
                  <td className="px-3 py-2 text-gray-600">{statsText(run)}</td>
                  <td className="px-3 py-2">
                    <Link to={`/runs/${run.id}`} className="text-indigo-700 underline">
                      View listings
                    </Link>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-gray-400">
                    No runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
