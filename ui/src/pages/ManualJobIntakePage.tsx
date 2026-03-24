import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { manualIngest } from "../api";

type IntakeForm = {
  title: string;
  company: string;
  location: string;
  apply_url: string;
  description: string;
  source_url: string;
  posted_at: string;
  salary_min: string;
  salary_max: string;
  workplace_type: string;
  employment_type: string;
};

const INITIAL_FORM: IntakeForm = {
  title: "",
  company: "",
  location: "",
  apply_url: "",
  description: "",
  source_url: "",
  posted_at: "",
  salary_min: "",
  salary_max: "",
  workplace_type: "",
  employment_type: "",
};

type SubmitState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; jobId: string | null; runId: string; status: string }
  | { kind: "duplicate"; runId: string }
  | { kind: "error"; message: string };

export default function ManualJobIntakePage() {
  const [form, setForm] = useState<IntakeForm>(INITIAL_FORM);
  const [validated, setValidated] = useState(false);
  const [submitState, setSubmitState] = useState<SubmitState>({ kind: "idle" });

  const requiredMissing = useMemo(() => {
    const missing: string[] = [];
    if (!form.title.trim()) missing.push("Job title");
    if (!form.company.trim()) missing.push("Company");
    if (!form.location.trim()) missing.push("Location");
    if (!form.apply_url.trim()) missing.push("Apply URL");
    if (!form.description.trim()) missing.push("Description");
    return missing;
  }, [form]);

  const buildPayload = () => {
    const out: Record<string, unknown> = {
      title: form.title.trim(),
      company: form.company.trim(),
      location: form.location.trim(),
      apply_url: form.apply_url.trim(),
      description: form.description.trim(),
    };
    if (form.source_url.trim()) out.source_url = form.source_url.trim();
    if (form.posted_at.trim()) out.posted_at = form.posted_at.trim();
    if (form.salary_min.trim()) out.salary_min = Number(form.salary_min);
    if (form.salary_max.trim()) out.salary_max = Number(form.salary_max);
    if (form.workplace_type.trim())
      out.workplace_type = form.workplace_type.trim();
    if (form.employment_type.trim())
      out.employment_type = form.employment_type.trim();
    return out;
  };

  const onChange = (key: keyof IntakeForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (validated) setValidated(false);
    if (submitState.kind !== "idle") setSubmitState({ kind: "idle" });
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setValidated(true);

    if (requiredMissing.length > 0) return;

    setSubmitState({ kind: "submitting" });
    try {
      const payload = buildPayload();
      const res = await manualIngest(
        payload as Parameters<typeof manualIngest>[0],
      );
      if (res.status === "DUPLICATE") {
        setSubmitState({ kind: "duplicate", runId: res.run_id });
      } else {
        setSubmitState({
          kind: "success",
          jobId: res.job_id,
          runId: res.run_id,
          status: res.status,
        });
      }
    } catch (err) {
      setSubmitState({
        kind: "error",
        message: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  const isSubmitting = submitState.kind === "submitting";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm">
        <Link to="/ready" className="text-indigo-600 hover:underline">
          &larr; Ready to Apply
        </Link>
      </div>

      <div className="rounded-xl border-2 border-indigo-100 bg-indigo-50/50 px-5 py-6">
        <h1 className="text-2xl font-bold text-gray-900">Manual Job Intake</h1>
        <p className="mt-1 text-sm text-gray-700">
          Enter the fields you extracted from a posting when URL ingest is not
          available.
        </p>
        <p className="mt-1 text-xs text-gray-600">
          Required: title, company, location, apply URL, description.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
      >
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Job title *</div>
            <input
              value={form.title}
              onChange={(e) => onChange("title", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Company *</div>
            <input
              value={form.company}
              onChange={(e) => onChange("company", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Location *</div>
            <input
              value={form.location}
              onChange={(e) => onChange("location", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Apply URL *</div>
            <input
              type="url"
              value={form.apply_url}
              onChange={(e) => onChange("apply_url", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
        </div>

        <label className="block text-sm">
          <div className="mb-1 font-medium text-gray-700">Description *</div>
          <textarea
            value={form.description}
            onChange={(e) => onChange("description", e.target.value)}
            rows={8}
            className="w-full rounded border border-gray-300 px-3 py-2"
            disabled={isSubmitting}
          />
        </label>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Source URL</div>
            <input
              type="url"
              value={form.source_url}
              onChange={(e) => onChange("source_url", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Posted at</div>
            <input
              type="datetime-local"
              value={form.posted_at}
              onChange={(e) => onChange("posted_at", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Salary min</div>
            <input
              type="number"
              value={form.salary_min}
              onChange={(e) => onChange("salary_min", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Salary max</div>
            <input
              type="number"
              value={form.salary_max}
              onChange={(e) => onChange("salary_max", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Workplace type</div>
            <select
              value={form.workplace_type}
              onChange={(e) => onChange("workplace_type", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            >
              <option value="">Select</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">
              Employment type
            </div>
            <select
              value={form.employment_type}
              onChange={(e) => onChange("employment_type", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
              disabled={isSubmitting}
            >
              <option value="">Select</option>
              <option value="full_time">Full-time</option>
              <option value="part_time">Part-time</option>
              <option value="contract">Contract</option>
              <option value="internship">Internship</option>
            </select>
          </label>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? "Submitting\u2026" : "Submit Job"}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => {
              setForm(INITIAL_FORM);
              setValidated(false);
              setSubmitState({ kind: "idle" });
            }}
            className="rounded border border-gray-300 px-4 py-2 text-sm"
          >
            Reset
          </button>
        </div>

        {validated && requiredMissing.length > 0 && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            Missing required fields: {requiredMissing.join(", ")}
          </div>
        )}

        {submitState.kind === "success" && (
          <div className="space-y-2 rounded border border-green-200 bg-green-50 p-3">
            <p className="text-sm font-medium text-green-800">
              Job ingested successfully. Pipeline started.
            </p>
            {submitState.jobId && (
              <p className="text-sm text-green-700">
                <Link
                  to={`/jobs/${submitState.jobId}`}
                  className="underline hover:text-green-900"
                >
                  View job &rarr;
                </Link>
              </p>
            )}
            <p className="text-xs text-green-600">
              Run ID: {submitState.runId}
            </p>
          </div>
        )}

        {submitState.kind === "duplicate" && (
          <div className="rounded border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
            This job already exists (duplicate detected). Run ID:{" "}
            {submitState.runId}
          </div>
        )}

        {submitState.kind === "error" && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            Error: {submitState.message}
          </div>
        )}
      </form>
    </div>
  );
}
