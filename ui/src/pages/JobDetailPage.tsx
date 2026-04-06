import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  updateJobStatus,
  fetchJob,
  triggerGenerateResume,
  type JobDetail,
} from "../api";
import ArtifactViewer from "../components/ArtifactViewer";
import ScoreBreakdown from "../components/ScoreBreakdown";
import StatusBadge from "../components/StatusBadge";
import SourceRoleBadge from "../components/SourceRoleBadge";
import { notifyError } from "../notify";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (options?: { background?: boolean; suppressError?: boolean }) => {
    if (!id) return;
    if (!options?.background) {
      setLoading(true);
    }
    if (!options?.suppressError) {
      setError(null);
    }
    try {
      const jobData = await fetchJob(id);
      setJob(jobData);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load job details";
      if (!options?.suppressError) {
        setError(message);
        notifyError(message);
      }
    } finally {
      if (!options?.background) {
        setLoading(false);
      }
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const status = (job?.latest_generation_run?.status || "").toLowerCase();
    if (status !== "queued" && status !== "running" && status !== "pending") {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      void load({ background: true, suppressError: true });
    }, 1500);
    return () => window.clearTimeout(timeoutId);
  }, [job?.latest_generation_run?.id, job?.latest_generation_run?.status, load]);

  const handleGenerateResume = useCallback(async () => {
    if (!id) return;
    setGenerating(true);
    setError(null);
    try {
      await triggerGenerateResume(id);
      await load({ background: true, suppressError: true });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Resume generation failed";
      setError(message);
      notifyError(message);
    } finally {
      setGenerating(false);
    }
  }, [id, load]);

  const handleAction = async (status: string) => {
    if (!job) return;
    try {
      await updateJobStatus(job.id, status);
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

  const canSave = job.user_status === "NEW" || job.user_status === "ARCHIVED";
  const canArchive = job.user_status === "NEW" || job.user_status === "SAVED";
  const canApply = job.user_status === "NEW" || job.user_status === "SAVED";
  const canGenerateResume =
    job.pipeline_status === "ATS_ANALYZED" || job.pipeline_status === "RESUME_READY";

  const readyToApply = job.artifact_availability && job.apply_url;
  const readyArtifact = job.artifacts?.find(
    (a) => a.is_primary && (a.generation_status || "").toLowerCase() === "success"
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Link to="/ready" className="text-sm text-indigo-600 hover:underline">
          ← Ready to Apply
        </Link>
        <span className="text-gray-400">|</span>
        <Link to="/jobs" className="text-sm text-indigo-600 hover:underline">
          All Jobs
        </Link>
      </div>

      {readyToApply && (
        <div className="rounded-lg border-2 border-indigo-200 bg-indigo-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-base font-semibold text-indigo-900">Ready to Apply</h2>
            <span className="rounded bg-indigo-200 px-2 py-0.5 text-xs font-medium text-indigo-900">
              Manual step — you apply
            </span>
          </div>
          <p className="mb-3 text-sm text-indigo-800">
            Download the tailored resume, open the application link below, and submit manually. JobBot never auto-submits.
          </p>
          <div className="flex flex-wrap gap-3">
            {readyArtifact && (
              <>
                <a
                  href={readyArtifact.download_url}
                  download
                  className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 no-underline"
                >
                  Download Resume
                </a>
                <a
                  href={readyArtifact.preview_url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded border border-indigo-600 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 no-underline"
                >
                  Preview Resume
                </a>
              </>
            )}
            <a
              href={job.apply_url!}
              target="_blank"
              rel="noreferrer"
              className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 no-underline"
              title="Opens external application page — you apply manually"
            >
              Open Application ↗
            </a>
          </div>
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{job.title}</h1>
          <p className="text-sm text-gray-600">{job.company}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge status={job.user_status} />
            <SourceRoleBadge source={job.source} />
            {job.pipeline_status && job.pipeline_status !== "SCORED" && job.pipeline_status !== "INGESTED" && (
              <span className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200">
                Pipeline: {job.pipeline_status}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canSave && (
            <button
              onClick={() => void handleAction("SAVED")}
              className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700"
            >
              Save
            </button>
          )}
          {canApply && (
            <button
              onClick={() => void handleAction("APPLIED")}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Mark Applied
            </button>
          )}
          {canArchive && (
            <button
              onClick={() => void handleAction("ARCHIVED")}
              className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              Archive
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
            {job.url && (
              <a href={job.url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">
                Open job listing
              </a>
            )}
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
              <dd className="text-right text-gray-900">{job.company}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Location</dt>
              <dd className="text-right text-gray-900">{job.location ?? "N/A"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Source / Provenance</dt>
              <dd className="text-right"><SourceRoleBadge source={job.source} /></dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Score</dt>
              <dd className="text-right text-gray-900">{job.score.toFixed(2)}</dd>
            </div>
            {job.ats_gaps?.ats_compatibility_score != null && (
              <div className="flex justify-between gap-4">
                <dt className="text-gray-500">ATS Match</dt>
                <dd className="text-right text-gray-900">{job.ats_gaps.ats_compatibility_score.toFixed(1)}%</dd>
              </div>
            )}
          </dl>
        </section>
      </div>

      <ScoreBreakdown
        scoreBreakdown={
          job.score_breakdown?.raw
            ? (job.score_breakdown.raw as Record<string, number>)
            : job.score_breakdown
              ? {
                  ...(job.score_breakdown.title_relevance != null && { title_relevance: job.score_breakdown.title_relevance }),
                  ...(job.score_breakdown.seniority_fit != null && { seniority_fit: job.score_breakdown.seniority_fit }),
                  ...(job.score_breakdown.tech_stack != null && { tech_stack: job.score_breakdown.tech_stack }),
                  ...(job.score_breakdown.location_remote != null && { location_remote: job.score_breakdown.location_remote }),
                }
              : null
        }
        atsBreakdown={
          job.ats_gaps
            ? {
                skills_found: job.ats_gaps.found_keywords ?? [],
                skills_missing: job.ats_gaps.missing_keywords ?? [],
                ...(job.ats_gaps.ats_compatibility_score != null && { keyword_overlap_pct: job.ats_gaps.ats_compatibility_score }),
              }
            : null
        }
      />

      {job.persona && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-lg font-semibold">Persona Classification</h2>
          <p className="text-sm text-gray-700">
            <span className="font-medium">{job.persona.matched_persona ?? "—"}</span>
            {job.persona.persona_confidence != null && (
              <span className="ml-2 text-gray-500">
                ({(job.persona.persona_confidence * 100).toFixed(0)}% confidence)
              </span>
            )}
          </p>
          {job.persona.persona_rationale && (
            <p className="mt-2 text-sm text-gray-600 italic">{job.persona.persona_rationale}</p>
          )}
        </section>
      )}

      <ArtifactViewer
        artifacts={job.artifacts ?? []}
        latestGenerationRun={job.latest_generation_run}
        onGenerateResume={handleGenerateResume}
        generating={generating}
        canGenerateResume={canGenerateResume}
      />
    </div>
  );
}
