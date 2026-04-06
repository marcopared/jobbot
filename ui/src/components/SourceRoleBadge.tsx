/** Infer canonical vs discovery from source. Backend may not return source_role in list items. */
export function sourceRoleLabel(source: string | null): string | null {
  if (!source) return null;
  const s = source.toLowerCase();
  if (["greenhouse", "lever", "ashby"].includes(s)) return "Canonical ATS";
  if (
    ["agg1", "serp1", "jobspy", "linkedin_jobs", "wellfound", "builtinnyc", "builtin_nyc", "yc"].includes(s)
  )
    return "Discovery";
  return null;
}

interface Props {
  source: string | null;
  className?: string;
}

export default function SourceRoleBadge({ source, className = "" }: Props) {
  const role = sourceRoleLabel(source);
  if (!role) return <span className={`text-gray-500 text-xs ${className}`}>{source ?? "—"}</span>;
  const isCanonical = role === "Canonical ATS";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${className} ${
        isCanonical
          ? "bg-green-100 text-green-800 border border-green-200"
          : "bg-amber-100 text-amber-800 border border-amber-200"
      }`}
      title={`Source: ${source} · Role: ${role}`}
    >
      {role}
    </span>
  );
}
