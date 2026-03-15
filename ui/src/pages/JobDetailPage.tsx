import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  approveJob,
  fetchJob,
  rejectJob,
  type JobDetail,
} from "../api";
import ArtifactViewer from "../components/ArtifactViewer";
import ScoreBreakdown from "../components/ScoreBreakdown";
import StatusBadge from "../components/StatusBadge";
import { notifyError } from "../notify";

type ArtifactRow = {
  id: string;
  kind: string;
  label: string;
  createdAt?: string | null;
};

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const jobData = await fetchJob(id);
      setJob(jobData);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load job details";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const artifacts: ArtifactRow[] = []; // Intentionally left empty or can map job artifacts if available

  const handleAction = async (action: "approve" | "reject") => {
    if (!job) return;
    try {
      if (action === "approve") await approveJob(job.id);
      if (action === "reject") await rejectJob(job.id);
      await load();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Action failed";
      setError(message);
      notifyError(message);
    }
  };

  if (!id) return <div className="text-sm text-gray-500">Missing job id.</div>;
  if (loading)
    return (
      <div className="space-y-2 rounded border border-gray-200 bg-white p-6">
        <div className="h-5 w-1/3 animate-pulse rounded bg-gray-200" />
        <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-gray-200" />
      </div>
    );
  if (!job) return <div className="text-sm text-gray-500">Job not found.</div>;

  const canApprove = job.status === "NEW" || job.status === "SCORED";
  const canReject = job.status === "NEW" || job.status === "SCORED" || job.status === "APPROVED";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{job.title}</h1>
          <p className="text-sm text-gray-600">{job.company_name_raw}</p>
          <div className="mt-2">
            <StatusBadge status={job.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canApprove && (
            <button
              onClick={() => void handleAction("approve")}
              className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700"
            >
              Approve
            </button>
          )}
          {canReject && (
            <button
              onClick={() => void handleAction("reject")}
              className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              Reject
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="rounded-lg border border-gray-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-2 text-lg font-semibold">Job Description</h2>
          <div className="prose max-w-none text-sm text-gray-700 whitespace-pre-wrap">
            {job.description || "No description available."}
          </div>
          <div className="mt-4 flex gap-4 text-sm">
            <a href={job.url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">
              Open job listing
            </a>
            {job.apply_url && (
              <a href={job.apply_url} target="_blank" rel="noreferrer" className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 no-underline">
                Open Application
              </a>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-lg font-semibold">Company Info</h2>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Company</dt>
              <dd className="text-right text-gray-900">{job.company_name_raw}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Location</dt>
              <dd className="text-right text-gray-900">{job.location ?? "N/A"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Source</dt>
              <dd className="text-right text-gray-900">{job.source}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Score</dt>
              <dd className="text-right text-gray-900">{job.score_total.toFixed(2)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">ATS Match</dt>
              <dd className="text-right text-gray-900">{job.ats_match_score.toFixed(1)}%</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-2 text-base font-semibold text-gray-900">Raw Scrape Payload (JobSpy)</h3>
        {job.source_payload_json ? (
          <div className="space-y-3">
            <div className="overflow-x-auto rounded border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-gray-600">Column</th>
                    <th className="px-3 py-2 text-left font-semibold text-gray-600">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {Object.entries(job.source_payload_json)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([key, value]) => (
                      <tr key={key}>
                        <td className="px-3 py-2 font-mono text-xs text-gray-700">{key}</td>
                        <td className="px-3 py-2 text-gray-900 break-all">
                          {value === null ? "null" : typeof value === "object" ? JSON.stringify(value) : String(value)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <details className="rounded border border-gray-200 bg-gray-50 p-2">
              <summary className="cursor-pointer text-sm font-medium text-gray-700">
                View raw JSON
              </summary>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-gray-900 p-3 text-xs text-gray-100">
                {JSON.stringify(job.source_payload_json, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <p className="text-sm text-gray-600">
            No raw scrape payload is stored for this job yet. Run a new scrape to populate JobSpy columns.
          </p>
        )}
      </section>

      <ScoreBreakdown
        scoreBreakdown={job.score_breakdown_json}
        atsBreakdown={job.ats_match_breakdown_json}
      />

      <ArtifactViewer artifacts={artifacts} />
    </div>
  );
}
