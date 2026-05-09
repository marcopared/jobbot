type ArtifactItem = {
  id: string;
  kind: string;
  filename: string;
  format: string | null;
  persona_name: string | null;
  generation_status: string | null;
  created_at: string | null;
  artifact_role: string | null;
  is_primary: boolean;
  payload_version: string | null;
  inputs_hash: string | null;
  fit_status: string | null;
  evidence_completeness: {
    summary: string;
    source_kind: string | null;
    total_sources: number;
    present_sources: number;
    required_sources: number;
    required_present: number;
    optional_sources: number;
    optional_present: number;
    missing_optional_sources: string[];
  } | null;
  download_url: string;
  preview_url: string;
};

type Props = {
  artifacts: ArtifactItem[];
  latestGenerationRun?: {
    id: string;
    status: string;
    triggered_by: string | null;
    created_at: string | null;
    finished_at: string | null;
    failure_reason: string | null;
    artifact_id: string | null;
  } | null;
  onGenerateResume?: () => void;
  generating?: boolean;
  canGenerateResume?: boolean;
};

function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function statusLabel(status: string | null): string {
  if (!status) return "Unknown";
  switch (status.toLowerCase()) {
    case "success":
      return "Ready";
    case "queued":
    case "running":
    case "pending":
      return "Generating…";
    case "failed":
      return "Failed";
    default:
      return status.replace(/_/g, " ");
  }
}

function fitStatusLabel(status: string | null): string | null {
  if (!status) return null;
  switch (status) {
    case "fit_success_one_page":
      return "One-page fit";
    case "fit_success_multi_page_fallback":
      return "Multi-page fallback";
    case "fit_failed_overflow":
      return "Overflow";
    default:
      return status.replace(/_/g, " ");
  }
}

function shortHash(value: string | null): string | null {
  if (!value) return null;
  return value.length <= 10 ? value : value.slice(0, 10);
}

function sidecarLabel(artifact: ArtifactItem): string {
  switch (artifact.artifact_role) {
    case "resume_payload":
      return "Payload JSON";
    case "resume_diagnostics":
      return "Diagnostics JSON";
    default:
      return artifact.filename || "Supporting file";
  }
}

export default function ArtifactViewer({
  artifacts,
  latestGenerationRun = null,
  onGenerateResume,
  generating = false,
  canGenerateResume = false,
}: Props) {
  const generationRunStatus = (latestGenerationRun?.status || "").toLowerCase();
  const hasPendingGenerationRun =
    generationRunStatus === "queued" ||
    generationRunStatus === "running" ||
    generationRunStatus === "pending";
  const hasPending = artifacts.some((a) => {
    const s = (a.generation_status || "").toLowerCase();
    return s === "queued" || s === "running" || s === "pending";
  }) || hasPendingGenerationRun;
  const primaryArtifacts = artifacts.filter((artifact) => artifact.is_primary);
  const sidecarArtifacts = artifacts.filter((artifact) => !artifact.is_primary);

  const buttonEnabled = canGenerateResume && !generating && !hasPending;
  const showGenerationStatus =
    latestGenerationRun != null &&
    (hasPendingGenerationRun || generationRunStatus === "failed");

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="mb-3 text-base font-semibold text-gray-900">Resume</h3>
      {showGenerationStatus && (
        <div
          className={
            generationRunStatus === "failed"
              ? "mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700"
              : "mb-3 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
          }
        >
          <p className="font-medium">
            {generationRunStatus === "failed"
              ? "Latest resume generation failed"
              : "Resume generation in progress"}
          </p>
          <p className="mt-1 text-xs">
            Status: {statusLabel(latestGenerationRun.status)}
            {latestGenerationRun.created_at
              ? ` · requested ${formatDate(latestGenerationRun.created_at)}`
              : ""}
            {latestGenerationRun.finished_at
              ? ` · finished ${formatDate(latestGenerationRun.finished_at)}`
              : ""}
          </p>
          {generationRunStatus === "queued" && (
            <p className="mt-1 text-xs">
              The request is queued. JobBot will update this panel when the worker starts and when
              artifacts are ready.
            </p>
          )}
          {generationRunStatus === "running" && (
            <p className="mt-1 text-xs">
              The worker is generating grounded resume artifacts from inventory-backed evidence.
            </p>
          )}
          {generationRunStatus === "failed" && latestGenerationRun.failure_reason && (
            <p className="mt-1 text-xs">{latestGenerationRun.failure_reason}</p>
          )}
        </div>
      )}
      {primaryArtifacts.length === 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">No resume generated yet.</p>
          {onGenerateResume && (
            <>
              <button
                onClick={onGenerateResume}
                disabled={!buttonEnabled}
                className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {generating ? "Generating…" : "Generate Resume"}
              </button>
              {!buttonEnabled && !generating && !hasPending && (
                <p className="text-xs text-gray-500">
                  Resume generation becomes available after ATS analysis completes.
                </p>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <ul className="space-y-2">
            {primaryArtifacts.map((artifact) => {
              const ready = (artifact.generation_status || "").toLowerCase() === "success";
              const fitLabel = fitStatusLabel(artifact.fit_status);
              const hashLabel = shortHash(artifact.inputs_hash);
              return (
                <li
                  key={artifact.id}
                  className="flex flex-col gap-1 rounded border border-gray-100 p-2 text-sm md:flex-row md:items-center md:justify-between"
                >
                  <div>
                    <p className="font-medium text-gray-800">
                      {artifact.persona_name
                        ? `Resume (${artifact.persona_name})`
                        : artifact.filename || "Resume"}
                    </p>
                    <p className="text-xs text-gray-500">
                      {artifact.kind} · {formatDate(artifact.created_at)} ·{" "}
                      <span
                        className={
                          ready
                            ? "text-green-600"
                            : (artifact.generation_status || "").toLowerCase() === "failed"
                              ? "text-red-600"
                              : "text-amber-600"
                        }
                      >
                        {statusLabel(artifact.generation_status)}
                      </span>
                    </p>
                    {(artifact.payload_version ||
                      hashLabel ||
                      fitLabel ||
                      artifact.evidence_completeness?.summary) && (
                      <p className="mt-1 text-xs text-gray-500">
                        {artifact.payload_version ? `Payload ${artifact.payload_version}` : null}
                        {artifact.payload_version &&
                        (hashLabel || fitLabel || artifact.evidence_completeness?.summary)
                          ? " · "
                          : ""}
                        {hashLabel ? `Inputs ${hashLabel}` : null}
                        {hashLabel && (fitLabel || artifact.evidence_completeness?.summary)
                          ? " · "
                          : ""}
                        {fitLabel ? fitLabel : null}
                        {fitLabel && artifact.evidence_completeness?.summary ? " · " : ""}
                        {artifact.evidence_completeness?.summary ?? null}
                      </p>
                    )}
                  </div>
                  <div className="inline-flex gap-2">
                    {ready ? (
                      <>
                        <a
                          href={artifact.preview_url}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                        >
                          Preview
                        </a>
                        <a
                          href={artifact.download_url}
                          download
                          className="rounded bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-700"
                        >
                          Download
                        </a>
                      </>
                    ) : (
                      <span className="text-xs text-gray-500 italic">
                        {(artifact.generation_status || "").toLowerCase() === "failed"
                          ? "Generation failed"
                          : "Processing…"}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          {sidecarArtifacts.length > 0 && (
            <div className="rounded border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Generation Details
              </p>
              <ul className="mt-2 space-y-2">
                {sidecarArtifacts.map((artifact) => {
                  const ready = (artifact.generation_status || "").toLowerCase() === "success";
                  return (
                    <li
                      key={artifact.id}
                      className="flex flex-col gap-1 text-sm md:flex-row md:items-center md:justify-between"
                    >
                      <div>
                        <p className="font-medium text-gray-700">{sidecarLabel(artifact)}</p>
                        <p className="text-xs text-gray-500">
                          {(artifact.format || artifact.kind).toUpperCase()} · {formatDate(artifact.created_at)}
                        </p>
                      </div>
                      <div className="inline-flex gap-2">
                        {ready ? (
                          <>
                            <a
                              href={artifact.preview_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                            >
                              Preview
                            </a>
                            <a
                              href={artifact.download_url}
                              download
                              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                            >
                              Download
                            </a>
                          </>
                        ) : (
                          <span className="text-xs text-gray-500 italic">Processing…</span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
      {onGenerateResume && primaryArtifacts.length > 0 && !hasPending && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
          <button
            onClick={onGenerateResume}
            disabled={!buttonEnabled}
            className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? "Generating…" : "Regenerate Resume"}
          </button>
          {!buttonEnabled && !generating && !hasPending && (
            <p className="text-xs text-gray-500">
              Resume generation becomes available after ATS analysis completes.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
