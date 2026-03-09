type ArtifactItem = {
  id: string;
  kind: string;
  label: string;
  createdAt?: string | null;
};

type Props = {
  artifacts: ArtifactItem[];
};

function formatDate(value?: string | null): string {
  if (!value) return "N/A";
  return new Date(value).toLocaleString();
}

export default function ArtifactViewer({ artifacts }: Props) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="mb-3 text-base font-semibold text-gray-900">Artifacts</h3>
      {artifacts.length === 0 ? (
        <p className="text-sm text-gray-500">No artifacts available.</p>
      ) : (
        <ul className="space-y-2">
          {artifacts.map((artifact) => (
            <li
              key={`${artifact.id}-${artifact.kind}`}
              className="flex flex-col gap-1 rounded border border-gray-100 p-2 text-sm md:flex-row md:items-center md:justify-between"
            >
              <div>
                <p className="font-medium text-gray-800">{artifact.label}</p>
                <p className="text-xs text-gray-500 capitalize">
                  {artifact.kind} · {formatDate(artifact.createdAt)}
                </p>
              </div>
              <div className="inline-flex gap-2">
                <a
                  href={`/api/artifacts/${artifact.id}/preview`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                >
                  Preview
                </a>
                <a
                  href={`/api/artifacts/${artifact.id}/download`}
                  className="rounded bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-700"
                >
                  Download
                </a>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
