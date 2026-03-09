type Props = {
  scoreBreakdown: Record<string, number> | null;
  atsBreakdown: Record<string, unknown> | null;
};

function fmtKey(key: string): string {
  return key.replace(/_/g, " ");
}

export default function ScoreBreakdown({ scoreBreakdown, atsBreakdown }: Props) {
  const scoreItems = Object.entries(scoreBreakdown ?? {});
  const atsSkillsFound = Array.isArray(atsBreakdown?.skills_found)
    ? (atsBreakdown?.skills_found as string[])
    : [];
  const atsSkillsMissing = Array.isArray(atsBreakdown?.skills_missing)
    ? (atsBreakdown?.skills_missing as string[])
    : [];

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-base font-semibold text-gray-900">Score Breakdown</h3>
        {scoreItems.length === 0 ? (
          <p className="text-sm text-gray-500">No score breakdown available.</p>
        ) : (
          <div className="space-y-2">
            {scoreItems.map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-sm">
                <span className="text-gray-600 capitalize">{fmtKey(key)}</span>
                <span className="font-medium tabular-nums text-gray-900">{value.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-base font-semibold text-gray-900">ATS Match Details</h3>
        {!atsBreakdown ? (
          <p className="text-sm text-gray-500">No ATS match breakdown available.</p>
        ) : (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-2">
              <span className="rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-800">
                Found: {atsSkillsFound.length}
              </span>
              <span className="rounded bg-yellow-100 px-2 py-1 text-xs font-medium text-yellow-800">
                Missing: {atsSkillsMissing.length}
              </span>
              {"keyword_overlap_pct" in atsBreakdown && (
                <span className="rounded bg-indigo-100 px-2 py-1 text-xs font-medium text-indigo-800">
                  Overlap: {String(atsBreakdown.keyword_overlap_pct)}%
                </span>
              )}
            </div>
            <div>
              <p className="mb-1 font-medium text-gray-700">Skills Found</p>
              <p className="text-gray-600">
                {atsSkillsFound.length > 0 ? atsSkillsFound.join(", ") : "None"}
              </p>
            </div>
            <div>
              <p className="mb-1 font-medium text-gray-700">Skills Missing</p>
              <p className="text-gray-600">
                {atsSkillsMissing.length > 0 ? atsSkillsMissing.join(", ") : "None"}
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
