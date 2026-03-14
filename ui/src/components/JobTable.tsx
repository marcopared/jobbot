import type { Job } from "../api";
import { Link } from "react-router-dom";
import StatusBadge from "./StatusBadge";

interface Props {
  jobs: Job[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  onAction: (id: string, action: "approve" | "reject") => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function JobTable({ jobs, selected, onToggle, onToggleAll, onAction }: Props) {
  const allSelected = jobs.length > 0 && jobs.every((j) => selected.has(j.id));

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="w-10 px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                className="rounded border-gray-300"
              />
            </th>
            <th className="px-3 py-3 text-left font-semibold text-gray-600">Title</th>
            <th className="px-3 py-3 text-left font-semibold text-gray-600 hidden md:table-cell">
              Company
            </th>
            <th className="px-3 py-3 text-left font-semibold text-gray-600 hidden lg:table-cell">
              Source
            </th>
            <th className="px-3 py-3 text-right font-semibold text-gray-600">Score</th>
            <th className="px-3 py-3 text-left font-semibold text-gray-600">Status</th>
            <th className="px-3 py-3 text-left font-semibold text-gray-600 hidden lg:table-cell">
              Scraped
            </th>
            <th className="px-3 py-3 text-right font-semibold text-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {jobs.map((job) => (
            <tr key={job.id} className="hover:bg-gray-50 transition">
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={selected.has(job.id)}
                  onChange={() => onToggle(job.id)}
                  className="rounded border-gray-300"
                />
              </td>
              <td className="px-3 py-2 max-w-xs">
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline font-medium truncate block"
                  title={job.title}
                >
                  {job.title}
                </a>
                <Link to={`/jobs/${job.id}`} className="text-xs text-indigo-700 underline">
                  View details
                </Link>
                <span className="md:hidden text-xs text-gray-500">{job.company_name_raw}</span>
              </td>
              <td className="px-3 py-2 text-gray-700 hidden md:table-cell">
                {job.company_name_raw}
              </td>
              <td className="px-3 py-2 text-gray-500 hidden lg:table-cell">{job.source}</td>
              <td className="px-3 py-2 text-right tabular-nums font-medium">
                {job.score_total.toFixed(1)}
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={job.status} />
              </td>
              <td className="px-3 py-2 text-gray-500 hidden lg:table-cell">
                {formatDate(job.scraped_at)}
              </td>
              <td className="px-3 py-2 text-right">
                <ActionButtons status={job.status} onAction={(a) => onAction(job.id, a)} />
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr>
              <td colSpan={8} className="px-3 py-8 text-center text-gray-400">
                No jobs found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ActionButtons({
  status,
  onAction,
}: {
  status: string;
  onAction: (a: "approve" | "reject") => void;
}) {
  const canApprove = status === "NEW" || status === "SCORED";
  const canReject = status === "NEW" || status === "SCORED" || status === "APPROVED";

  return (
    <span className="inline-flex gap-1">
      {canApprove && (
        <button
          onClick={() => onAction("approve")}
          className="rounded bg-green-600 px-2 py-1 text-xs font-medium text-white hover:bg-green-700 transition"
        >
          Approve
        </button>
      )}
      {canReject && (
        <button
          onClick={() => onAction("reject")}
          className="rounded bg-red-500 px-2 py-1 text-xs font-medium text-white hover:bg-red-600 transition"
        >
          Reject
        </button>
      )}
    </span>
  );
}
