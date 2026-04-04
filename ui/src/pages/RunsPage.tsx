import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchRuns,
  fetchSourceAdapterCapabilities,
  runScrapeNow,
  runDiscovery,
  runIngestion,
  type Run,
  type SourceAdapterCapability,
  runSourceAdapter,
} from "../api";
import EmptyState from "../components/EmptyState";
import { notifyError } from "../notify";

function formatDate(value: string | null): string {
  if (!value) return "N/A";
  return new Date(value).toLocaleString();
}

function formatDuration(
  startedAt: string | null,
  finishedAt: string | null,
): string {
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

type SourceAdapterFamily = "public_board" | "portfolio_board" | "auth_board";

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [sourceCapabilities, setSourceCapabilities] = useState<
    SourceAdapterCapability[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [discoveryConnector, setDiscoveryConnector] = useState<
    "agg1" | "serp1"
  >("agg1");
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryLocation, setDiscoveryLocation] = useState("");
  const [discoveryResultsPerPage, setDiscoveryResultsPerPage] = useState("20");
  const [discoveryTriggering, setDiscoveryTriggering] = useState(false);
  const [lastTriggeredRunId, setLastTriggeredRunId] = useState<string | null>(
    null,
  );

  const [ingestConnector, setIngestConnector] = useState<
    "greenhouse" | "lever" | "ashby"
  >("greenhouse");
  const [ingestCompany, setIngestCompany] = useState("");
  const [ingestBoardToken, setIngestBoardToken] = useState("");
  const [ingestClientName, setIngestClientName] = useState("");
  const [ingestJobBoardName, setIngestJobBoardName] = useState("");
  const [ingestTriggering, setIngestTriggering] = useState(false);

  const [sourceAdapterFamily, setSourceAdapterFamily] =
    useState<SourceAdapterFamily>("public_board");
  const [sourceAdapterName, setSourceAdapterName] = useState("");
  const [sourceAdapterMaxResults, setSourceAdapterMaxResults] = useState("25");
  const [sourceAdapterTriggering, setSourceAdapterTriggering] = useState(false);
  const [lastSourceAdapterRunId, setLastSourceAdapterRunId] = useState<
    string | null
  >(null);

  const hasRunning = useMemo(
    () => runs.some((r) => r.status === "RUNNING"),
    [runs],
  );

  const capabilityMap = useMemo(
    () => new Map(sourceCapabilities.map((item) => [item.source_name, item])),
    [sourceCapabilities],
  );

  const familyOptions = useMemo(() => {
    const seen = new Set<SourceAdapterFamily>();
    const ordered: SourceAdapterFamily[] = [];
    for (const item of sourceCapabilities) {
      if (seen.has(item.source_family)) continue;
      seen.add(item.source_family);
      ordered.push(item.source_family);
    }
    return ordered;
  }, [sourceCapabilities]);

  const sourceOptions = useMemo(
    () =>
      sourceCapabilities.filter(
        (item) => item.source_family === sourceAdapterFamily,
      ),
    [sourceCapabilities, sourceAdapterFamily],
  );

  const selectedSourceCapability = useMemo(
    () =>
      sourceOptions.find((item) => item.source_name === sourceAdapterName) ??
      null,
    [sourceAdapterName, sourceOptions],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [runsData, capabilitiesData] = await Promise.all([
        fetchRuns({ page: "1", per_page: "25" }),
        fetchSourceAdapterCapabilities(),
      ]);
      setRuns(runsData.items);
      setSourceCapabilities(capabilitiesData.items);
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

  useEffect(() => {
    if (!familyOptions.length) return;
    if (!familyOptions.includes(sourceAdapterFamily)) {
      setSourceAdapterFamily(familyOptions[0]);
    }
  }, [familyOptions, sourceAdapterFamily]);

  useEffect(() => {
    if (!sourceOptions.length) {
      if (sourceAdapterName) setSourceAdapterName("");
      return;
    }
    const hasSelected = sourceOptions.some(
      (item) => item.source_name === sourceAdapterName,
    );
    if (hasSelected) return;
    const nextSource = sourceOptions.find((item) => item.launch_enabled);
    setSourceAdapterName((nextSource ?? sourceOptions[0]).source_name);
  }, [sourceAdapterName, sourceOptions]);

  const onRunScrape = async () => {
    setTriggering(true);
    setError(null);
    try {
      await runScrapeNow();
      await load();
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Failed to trigger scrape";
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
      const data = await runDiscovery({
        connector: discoveryConnector,
        query: discoveryQuery.trim() || undefined,
        location: discoveryLocation.trim() || undefined,
        results_per_page:
          discoveryResultsPerPage.trim() &&
          !Number.isNaN(Number(discoveryResultsPerPage))
            ? Number(discoveryResultsPerPage)
            : undefined,
      });
      setLastTriggeredRunId(data.run_id);
      await load();
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Failed to trigger discovery";
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
      const message =
        e instanceof Error ? e.message : "Failed to trigger ingestion";
      setError(message);
      notifyError(message);
    } finally {
      setIngestTriggering(false);
    }
  };

  const onRunSourceAdapter = async () => {
    if (!selectedSourceCapability) {
      setError("Select a source adapter");
      return;
    }
    if (!selectedSourceCapability.launch_enabled) {
      setError(
        selectedSourceCapability.launch_reason || "This source is not launchable",
      );
      return;
    }
    setSourceAdapterTriggering(true);
    setError(null);
    try {
      const data = await runSourceAdapter({
        source_name: selectedSourceCapability.source_name,
        max_results:
          sourceAdapterMaxResults.trim() &&
          !Number.isNaN(Number(sourceAdapterMaxResults))
            ? Number(sourceAdapterMaxResults)
            : undefined,
      });
      setLastSourceAdapterRunId(data.run_id);
      await load();
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Failed to trigger source adapter run";
      setError(message);
      notifyError(message);
    } finally {
      setSourceAdapterTriggering(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Runs</h1>
          <p className="text-sm text-gray-600">
            Trigger JobSpy, legacy routes, or ingestion-v2 source adapters.
            Runs appear below.
          </p>
        </div>
        <Link
          to="/ready"
          className="inline-flex items-center rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 no-underline"
        >
          Open Ready to Apply
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            JobSpy Scrape
          </h2>
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
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            Discovery
          </h2>
          <p className="mb-3 text-xs text-gray-500">
            AGG-1 (Adzuna) or SERP1 (DataForSEO Google Jobs), feature-flagged.
          </p>
          <div className="space-y-2">
            <select
              value={discoveryConnector}
              onChange={(e) =>
                setDiscoveryConnector(e.target.value as "agg1" | "serp1")
              }
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            >
              <option value="agg1">AGG-1 (Adzuna)</option>
              <option value="serp1">SERP1 (DataForSEO)</option>
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
            <input
              type="number"
              min={1}
              max={50}
              placeholder="Results per page (default 20)"
              value={discoveryResultsPerPage}
              onChange={(e) => setDiscoveryResultsPerPage(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            />
            <p className="text-xs text-gray-500">
              {discoveryConnector === "agg1"
                ? "AGG-1 is medium-confidence discovery. Use focused query/location for cleaner candidates."
                : "SERP1 is lower-confidence discovery. Expect stricter generation gate and occasional provider timeouts."}
            </p>
            <button
              onClick={() => void onRunDiscovery()}
              disabled={discoveryTriggering}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {discoveryTriggering ? "Triggering…" : "Run Discovery"}
            </button>
            {lastTriggeredRunId && (
              <p className="text-xs text-green-700">
                Discovery started.{" "}
                <Link to={`/runs/${lastTriggeredRunId}`} className="underline">
                  View run
                </Link>
              </p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            Canonical Ingestion
          </h2>
          <p className="mb-3 text-xs text-gray-500">
            Greenhouse, Lever, or Ashby.
          </p>
          <div className="space-y-2">
            <select
              value={ingestConnector}
              onChange={(e) =>
                setIngestConnector(
                  e.target.value as "greenhouse" | "lever" | "ashby",
                )
              }
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

        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            Source Adapters
          </h2>
          <p className="mb-3 text-xs text-gray-500">
            Launch ingestion-v2 public-board or authenticated-board sources
            from the same operator console.
          </p>
          <div className="space-y-2">
            <select
              value={sourceAdapterFamily}
              onChange={(e) =>
                setSourceAdapterFamily(
                  e.target.value as
                    | "public_board"
                    | "portfolio_board"
                    | "auth_board",
                )
              }
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
              disabled={familyOptions.length === 0}
            >
              {familyOptions.map((family) => {
                const label =
                  sourceCapabilities.find(
                    (item) => item.source_family === family,
                  )?.family_label ?? family;
                return (
                  <option key={family} value={family}>
                    {label}
                  </option>
                );
              })}
            </select>
            <select
              value={sourceAdapterName}
              onChange={(e) => setSourceAdapterName(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
              disabled={sourceOptions.length === 0}
            >
              {sourceOptions.map((item) => (
                <option
                  key={item.source_name}
                  value={item.source_name}
                  disabled={!item.launch_enabled}
                >
                  {item.source_label}
                  {item.launch_enabled ? "" : " (unavailable)"}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              max={100}
              placeholder="Max results (default 25)"
              value={sourceAdapterMaxResults}
              onChange={(e) => setSourceAdapterMaxResults(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
            />
            {selectedSourceCapability ? (
              <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                <div>
                  backend: {selectedSourceCapability.backend_label} · role:{" "}
                  {selectedSourceCapability.source_role}
                </div>
                <div>
                  {selectedSourceCapability.requires_auth
                    ? "Requires authenticated browser session support."
                    : "Uses bounded public-board acquisition."}
                </div>
                {selectedSourceCapability.launch_reason && (
                  <div className="text-red-700">
                    Unavailable: {selectedSourceCapability.launch_reason}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-500">
                No source adapters available.
              </p>
            )}
            <button
              onClick={() => void onRunSourceAdapter()}
              disabled={
                sourceAdapterTriggering ||
                !selectedSourceCapability ||
                !selectedSourceCapability.launch_enabled
              }
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {sourceAdapterTriggering
                ? "Triggering…"
                : "Run Source Adapter"}
            </button>
            {lastSourceAdapterRunId && (
              <p className="text-xs text-green-700">
                Source adapter run started.{" "}
                <Link
                  to={`/runs/${lastSourceAdapterRunId}`}
                  className="underline"
                >
                  View run
                </Link>
              </p>
            )}
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
          description="Trigger a JobSpy scrape, a legacy run route, or a source-adapter run above. Runs will appear here as they complete."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Source
                </th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Status
                </th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Started
                </th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Duration
                </th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Stats
                </th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Error
                </th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">
                  Details
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-900">
                      {capabilityMap.get(run.source)?.source_label ?? run.source}
                    </div>
                    <div className="text-xs text-gray-500">
                      {capabilityMap.get(run.source)?.family_label ?? "Legacy route"}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        run.status === "RUNNING"
                          ? "bg-yellow-100 text-yellow-800"
                          : run.status === "SUCCESS"
                            ? "bg-green-100 text-green-800"
                            : run.status === "SKIPPED"
                              ? "bg-gray-100 text-gray-800"
                              : "bg-red-100 text-red-800"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">{formatDate(run.started_at)}</td>
                  <td className="px-3 py-2">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                  <td className="px-3 py-2 text-gray-600">{statsText(run)}</td>
                  <td className="px-3 py-2">
                    {run.error_text ? (
                      <span
                        className="text-xs text-red-700"
                        title={run.error_text}
                      >
                        {run.error_text.length > 80
                          ? `${run.error_text.slice(0, 80)}…`
                          : run.error_text}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">
                        No provider error
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      to={`/runs/${run.id}`}
                      className="text-indigo-700 underline"
                    >
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
