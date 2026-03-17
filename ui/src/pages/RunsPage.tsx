import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchRuns,
  runScrapeNow,
  runDiscovery,
  runIngestion,
  type Run,
} from "../api";
import EmptyState from "../components/EmptyState";
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

  const [discoveryConnector, setDiscoveryConnector] = useState<"agg1" | "serp1">("agg1");
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryLocation, setDiscoveryLocation] = useState("");
  const [discoveryTriggering, setDiscoveryTriggering] = useState(false);

  const [ingestConnector, setIngestConnector] = useState<"greenhouse" | "lever" | "ashby">("greenhouse");
  const [ingestCompany, setIngestCompany] = useState("");
  const [ingestBoardToken, setIngestBoardToken] = useState("");
  const [ingestClientName, setIngestClientName] = useState("");
  const [ingestJobBoardName, setIngestJobBoardName] = useState("");
  const [ingestTriggering, setIngestTriggering] = useState(false);

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

  const onRunDiscovery = async () => {
    setDiscoveryTriggering(true);
    setError(null);
    try {
      await runDiscovery({
        connector: discoveryConnector,
        query: discoveryQuery.trim() || undefined,
        location: discoveryLocation.trim() || undefined,
      });
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to trigger discovery";
      setError(message);
      notifyError(message);
    } finally {
      setDiscoveryTriggering(false);
    }
  };

  const onRunIngestion = async () => {
    if (!ingestCompany.trim()) {
      setError("Company name is required");
      return;
    }
    const body: Parameters<typeof runIngestion>[0] = {
      connector: ingestConnector,
      company_name: ingestCompany.trim(),
    };
    if (ingestConnector === "greenhouse" && ingestBoardToken.trim()) {
      body.board_token = ingestBoardToken.trim();
    }
    if (ingestConnector === "lever" && ingestClientName.trim()) {
      body.client_name = ingestClientName.trim();
    }
    if (ingestConnector === "ashby" && ingestJobBoardName.trim()) {
      body.job_board_name = ingestJobBoardName.trim();
    }
    setIngestTriggering(true);
    setError(null);
    try {
      await runIngestion(body);
      await load();
      setIngestCompany("");
      setIngestBoardToken("");
      setIngestClientName("");
      setIngestJobBoardName("");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to trigger ingestion";
      setError(message);
      notifyError(message);
    } finally {
      setIngestTriggering(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Runs</h1>
      <p className="text-sm text-gray-600">
        Trigger discovery, canonical ingestion, or JobSpy scrape. Runs appear below.
      </p>

      <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">JobSpy Scrape</h2>
          <p className="mb-3 text-xs text-gray-500">Broad scrape via JobSpy.</p>
          <button
            onClick={() => void onRunScrape()}
            disabled={triggering}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {triggering ? "Triggering…" : "Run Scrape"}
          </button>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">Discovery</h2>
          <p className="mb-3 text-xs text-gray-500">AGG-1 or SERP1 (feature-flagged).</p>
          <div className="space-y-2">
            <select
              value={discoveryConnector}
              onChange={(e) => setDiscoveryConnector(e.target.value as "agg1" | "serp1")}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            >
              <option value="agg1">AGG-1</option>
              <option value="serp1">SERP1</option>
            </select>
            <input
              type="text"
              placeholder="Query (optional)"
              value={discoveryQuery}
              onChange={(e) => setDiscoveryQuery(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            />
            <input
              type="text"
              placeholder="Location (optional)"
              value={discoveryLocation}
              onChange={(e) => setDiscoveryLocation(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            />
            <button
              onClick={() => void onRunDiscovery()}
              disabled={discoveryTriggering}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {discoveryTriggering ? "Triggering…" : "Run Discovery"}
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">Canonical Ingestion</h2>
          <p className="mb-3 text-xs text-gray-500">Greenhouse, Lever, or Ashby.</p>
          <div className="space-y-2">
            <select
              value={ingestConnector}
              onChange={(e) => setIngestConnector(e.target.value as "greenhouse" | "lever" | "ashby")}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            >
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
              <option value="ashby">Ashby</option>
            </select>
            <input
              type="text"
              placeholder="Company name *"
              value={ingestCompany}
              onChange={(e) => setIngestCompany(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            />
            {ingestConnector === "greenhouse" && (
              <input
                type="text"
                placeholder="Board token *"
                value={ingestBoardToken}
                onChange={(e) => setIngestBoardToken(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
              />
            )}
            {ingestConnector === "lever" && (
              <input
                type="text"
                placeholder="Client name *"
                value={ingestClientName}
                onChange={(e) => setIngestClientName(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
              />
            )}
            {ingestConnector === "ashby" && (
              <input
                type="text"
                placeholder="Job board name *"
                value={ingestJobBoardName}
                onChange={(e) => setIngestJobBoardName(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
              />
            )}
            <button
              onClick={() => void onRunIngestion()}
              disabled={ingestTriggering || !ingestCompany.trim()}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {ingestTriggering ? "Triggering…" : "Run Ingestion"}
            </button>
          </div>
        </div>
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
      ) : runs.length === 0 ? (
        <EmptyState
          title="No runs yet"
          description="Trigger a JobSpy scrape, discovery run, or canonical ingestion above. Runs will appear here as they complete."
        />
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
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
