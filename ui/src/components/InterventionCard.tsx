import { useMemo, useState } from "react";
import {
  abortIntervention,
  resolveIntervention,
  retryIntervention,
  type Intervention,
  type JobDetail,
} from "../api";
import { notifyError } from "../notify";

type Props = {
  intervention: Intervention;
  job?: JobDetail;
  onUpdated: () => Promise<void>;
};

const REASON_STYLES: Record<string, string> = {
  captcha: "bg-red-100 text-red-800 border-red-200",
  mfa: "bg-orange-100 text-orange-800 border-orange-200",
  unexpected_field: "bg-yellow-100 text-yellow-800 border-yellow-200",
  blocked: "bg-red-100 text-red-800 border-red-200",
  login_required: "bg-orange-100 text-orange-800 border-orange-200",
};

function formatDate(value: string | null): string {
  if (!value) return "N/A";
  return new Date(value).toLocaleString();
}

export default function InterventionCard({ intervention, job, onUpdated }: Props) {
  const [busy, setBusy] = useState(false);
  const [showResolve, setShowResolve] = useState(false);
  const [notes, setNotes] = useState("");
  const [expandedImg, setExpandedImg] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const screenshotUrl = useMemo(() => {
    if (!intervention.screenshot_artifact_id) return null;
    return `/api/artifacts/${intervention.screenshot_artifact_id}/preview`;
  }, [intervention.screenshot_artifact_id]);

  const reasonStyle =
    REASON_STYLES[intervention.reason] ?? "bg-gray-100 text-gray-700 border-gray-200";

  const handleResolve = async () => {
    setBusy(true);
    setError(null);
    try {
      await resolveIntervention(intervention.id, notes.trim() || undefined);
      setShowResolve(false);
      setNotes("");
      await onUpdated();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Resolve failed";
      setError(message);
      notifyError(message);
    } finally {
      setBusy(false);
    }
  };

  const handleAbort = async () => {
    setBusy(true);
    setError(null);
    try {
      await abortIntervention(intervention.id);
      await onUpdated();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Abort failed";
      setError(message);
      notifyError(message);
    } finally {
      setBusy(false);
    }
  };

  const handleRetry = async () => {
    setBusy(true);
    setError(null);
    try {
      await retryIntervention(intervention.id);
      await onUpdated();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Retry failed";
      setError(message);
      notifyError(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-gray-900">
            {job?.title ?? "Loading job..."}
          </h3>
          <p className="text-sm text-gray-600">{job?.company_name_raw ?? intervention.job_id}</p>
        </div>
        <span className={`rounded border px-2 py-1 text-xs font-medium ${reasonStyle}`}>
          {intervention.reason.replace(/_/g, " ")}
        </span>
      </div>

      {screenshotUrl ? (
        <button
          type="button"
          className="mb-3 block w-full overflow-hidden rounded border border-gray-200"
          onClick={() => setExpandedImg((v) => !v)}
        >
          <img
            src={screenshotUrl}
            alt="Intervention screenshot"
            className={`w-full object-cover ${expandedImg ? "max-h-[32rem]" : "max-h-52"}`}
          />
        </button>
      ) : (
        <div className="mb-3 rounded border border-dashed border-gray-300 p-3 text-sm text-gray-500">
          No screenshot available
        </div>
      )}

      <div className="space-y-1 text-sm">
        <p className="text-gray-700">
          <span className="font-medium">Created:</span> {formatDate(intervention.created_at)}
        </p>
        <p className="text-gray-700">
          <span className="font-medium">Status:</span> {intervention.status}
        </p>
        {intervention.last_url && (
          <p className="break-all text-gray-700">
            <span className="font-medium">Last URL:</span>{" "}
            <a
              href={intervention.last_url}
              target="_blank"
              rel="noreferrer"
              className="text-indigo-700 underline"
            >
              {intervention.last_url}
            </a>
          </p>
        )}
      </div>

      {error && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => setShowResolve((v) => !v)}
          className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          Resolve
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={handleAbort}
          className="rounded bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          Abort
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={handleRetry}
          className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          Retry Apply
        </button>
      </div>

      {showResolve && (
        <div className="mt-3 rounded border border-gray-200 bg-gray-50 p-3">
          <label className="mb-1 block text-xs font-medium text-gray-700">Optional notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
            placeholder="Resolved manually..."
          />
          <div className="mt-2">
            <button
              type="button"
              disabled={busy}
              onClick={handleResolve}
              className="rounded bg-green-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-800 disabled:opacity-50"
            >
              Confirm Resolve
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
