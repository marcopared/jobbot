import { Fragment, useCallback, useEffect, useState } from "react";
import {
  fetchApplication,
  fetchApplications,
  fetchJob,
  type Application,
  type ApplicationDetail,
  type JobDetail,
} from "../api";
import StatusBadge from "../components/StatusBadge";
import { notifyError } from "../notify";

const STATUSES = ["ALL", "STARTED", "SUBMITTED", "FAILED", "INTERVENTION_REQUIRED", "SKIPPED"];

function formatDate(value: string | null): string {
  if (!value) return "N/A";
  return new Date(value).toLocaleString();
}

export default function ApplicationsPage() {
  const [status, setStatus] = useState("ALL");
  const [items, setItems] = useState<Application[]>([]);
  const [jobsById, setJobsById] = useState<Record<string, JobDetail>>({});
  const [expanded, setExpanded] = useState<Record<string, ApplicationDetail | null>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { page: "1", per_page: "50" };
      if (status !== "ALL") params.status = status;
      const data = await fetchApplications(params);
      setItems(data.items);

      const uniqueJobIds = Array.from(new Set(data.items.map((i) => i.job_id)));
      const jobs = await Promise.all(
        uniqueJobIds.map(async (id) => {
          try {
            return await fetchJob(id);
          } catch {
            return null;
          }
        }),
      );
      const next: Record<string, JobDetail> = {};
      for (const job of jobs) {
        if (job) next[job.id] = job;
      }
      setJobsById(next);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load applications";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleRow = async (id: string) => {
    if (expanded[id] !== undefined) {
      setExpanded((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }
    try {
      const detail = await fetchApplication(id);
      setExpanded((prev) => ({ ...prev, [id]: detail }));
    } catch {
      setExpanded((prev) => ({ ...prev, [id]: null }));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Applications</h1>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === "ALL" ? "All Statuses" : s}
            </option>
          ))}
        </select>
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
          <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Job Title</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Company</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Status</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Method</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Started</th>
                <th className="px-3 py-3 text-left font-semibold text-gray-600">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((app) => {
                const job = jobsById[app.job_id];
                const duration =
                  app.started_at && app.finished_at
                    ? `${Math.max(
                        0,
                        Math.round(
                          (new Date(app.finished_at).getTime() -
                            new Date(app.started_at).getTime()) /
                            1000,
                        ),
                      )}s`
                    : "In progress";
                const detail = expanded[app.id];
                const isExpanded = app.id in expanded;
                return (
                  <Fragment key={app.id}>
                    <tr
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => void toggleRow(app.id)}
                    >
                      <td className="px-3 py-2">{job?.title ?? app.job_id}</td>
                      <td className="px-3 py-2 text-gray-700">{job?.company_name_raw ?? "N/A"}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={app.status} />
                      </td>
                      <td className="px-3 py-2 text-gray-600">{app.method}</td>
                      <td className="px-3 py-2 text-gray-600">{formatDate(app.started_at)}</td>
                      <td className="px-3 py-2 text-gray-600">{duration}</td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-gray-50">
                        <td colSpan={6} className="px-4 py-3">
                          <div className="space-y-2 text-sm">
                            <p>
                              <span className="font-medium">Error:</span>{" "}
                              {detail?.error_text ?? app.error_text ?? "None"}
                            </p>
                            <p>
                              <span className="font-medium">External App ID:</span>{" "}
                              {detail?.external_app_id ?? app.external_app_id ?? "N/A"}
                            </p>
                            <p className="break-all">
                              <span className="font-medium">Fields JSON:</span>{" "}
                              {JSON.stringify(detail?.fields_json ?? app.fields_json ?? {}, null, 2)}
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-gray-400">
                    No applications found.
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
