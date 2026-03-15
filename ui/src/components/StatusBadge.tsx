const COLORS: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-800",
  SCORED: "bg-indigo-100 text-indigo-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
  SAVED: "bg-yellow-100 text-yellow-800",
  APPLIED: "bg-emerald-100 text-emerald-800",
  ARCHIVED: "bg-gray-200 text-gray-800",
  // Legacy
  APPLY_QUEUED: "bg-yellow-100 text-yellow-800",
  APPLY_FAILED: "bg-red-200 text-red-900",
  INTERVENTION_REQUIRED: "bg-orange-100 text-orange-800",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = COLORS[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
