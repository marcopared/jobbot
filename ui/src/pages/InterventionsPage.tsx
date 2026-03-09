import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchInterventions, fetchJob, type Intervention, type JobDetail } from "../api";
import InterventionCard from "../components/InterventionCard";
import { notifyError } from "../notify";

const TABS = ["OPEN", "RESOLVED", "ABORTED"] as const;
type Tab = (typeof TABS)[number];

export default function InterventionsPage() {
  const [status, setStatus] = useState<Tab>("OPEN");
  const [items, setItems] = useState<Intervention[]>([]);
  const [jobsById, setJobsById] = useState<Record<string, JobDetail>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInterventions({
        status,
        page: "1",
        per_page: "50",
      });
      setItems(data.items);

      const uniqueJobIds = Array.from(new Set(data.items.map((i) => i.job_id)));
      const jobs = await Promise.all(
        uniqueJobIds.map(async (id) => {
          try {
            return await fetchJob(id);
          } catch {
            return null;
          }
        }),
      );
      const next: Record<string, JobDetail> = {};
      for (const job of jobs) {
        if (job) next[job.id] = job;
      }
      setJobsById(next);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load interventions";
      setError(message);
      notifyError(message);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const emptyMessage = useMemo(
    () => `No ${status.toLowerCase()} interventions found.`,
    [status],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Interventions</h1>
        <div className="inline-flex rounded border border-gray-300 bg-white p-1">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setStatus(tab)}
              className={`rounded px-3 py-1.5 text-sm font-medium ${
                status === tab ? "bg-indigo-600 text-white" : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-2 rounded border border-gray-200 bg-white p-6">
          <div className="h-4 w-1/3 animate-pulse rounded bg-gray-200" />
          <div className="h-40 w-full animate-pulse rounded bg-gray-100" />
          <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded border border-gray-200 bg-white p-6 text-center text-gray-500">
          {emptyMessage}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {items.map((intervention) => (
            <InterventionCard
              key={intervention.id}
              intervention={intervention}
              job={jobsById[intervention.job_id]}
              onUpdated={load}
            />
          ))}
        </div>
      )}
    </div>
  );
}
