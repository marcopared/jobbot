type ArtifactItem = {
  id: string;
  kind: string;
  filename: string;
  persona_name: string | null;
  generation_status: string | null;
  created_at: string | null;
  download_url: string;
  preview_url: string;
};

type Props = {
  artifacts: ArtifactItem[];
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

export default function ArtifactViewer({
  artifacts,
  onGenerateResume,
  generating = false,
  canGenerateResume = false,
}: Props) {
  const hasPending = artifacts.some((a) => {
    const s = (a.generation_status || "").toLowerCase();
    return s === "queued" || s === "running" || s === "pending";
  });

  const buttonEnabled = canGenerateResume && !generating && !hasPending;

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="mb-3 text-base font-semibold text-gray-900">Resume</h3>
      {artifacts.length === 0 ? (
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
        <ul className="space-y-2">
          {artifacts.map((artifact) => {
            const ready = (artifact.generation_status || "").toLowerCase() === "success";
            return (
              <li
                key={artifact.id}
                className="flex flex-col gap-1 rounded border border-gray-100 p-2 text-sm md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p className="font-medium text-gray-800">
                    {artifact.persona_name ? `Resume (${artifact.persona_name})` : artifact.filename || "Resume"}
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
      )}
      {onGenerateResume && artifacts.length > 0 && !hasPending && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
          <button
            onClick={onGenerateResume}
            disabled={!buttonEnabled}
            className="rounded border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? "Generating…" : "Regenerate Resume"}
          </button>
          {!buttonEnabled && !generating && (
            <p className="text-xs text-gray-500">
              Resume generation becomes available after ATS analysis completes.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
