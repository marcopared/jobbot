import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

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

export default function ManualJobIntakePage() {
  const [form, setForm] = useState<IntakeForm>(INITIAL_FORM);
  const [submitted, setSubmitted] = useState(false);

  const requiredMissing = useMemo(() => {
    const missing: string[] = [];
    if (!form.title.trim()) missing.push("Job title");
    if (!form.company.trim()) missing.push("Company");
    if (!form.location.trim()) missing.push("Location");
    if (!form.apply_url.trim()) missing.push("Apply URL");
    if (!form.description.trim()) missing.push("Description");
    return missing;
  }, [form]);

  const payloadPreview = useMemo(() => {
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
  }, [form]);

  const onChange = (key: keyof IntakeForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (submitted) setSubmitted(false);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  const canProceed = submitted && requiredMissing.length === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm">
        <Link to="/ready" className="text-indigo-600 hover:underline">
          ← Ready to Apply
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
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Company *</div>
            <input
              value={form.company}
              onChange={(e) => onChange("company", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Location *</div>
            <input
              value={form.location}
              onChange={(e) => onChange("location", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Apply URL *</div>
            <input
              type="url"
              value={form.apply_url}
              onChange={(e) => onChange("apply_url", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
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
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Posted at</div>
            <input
              type="datetime-local"
              value={form.posted_at}
              onChange={(e) => onChange("posted_at", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Salary min</div>
            <input
              type="number"
              value={form.salary_min}
              onChange={(e) => onChange("salary_min", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Salary max</div>
            <input
              type="number"
              value={form.salary_max}
              onChange={(e) => onChange("salary_max", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700">Workplace type</div>
            <select
              value={form.workplace_type}
              onChange={(e) => onChange("workplace_type", e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2"
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
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Validate Fields
          </button>
          <button
            type="button"
            onClick={() => {
              setForm(INITIAL_FORM);
              setSubmitted(false);
            }}
            className="rounded border border-gray-300 px-4 py-2 text-sm"
          >
            Reset
          </button>
        </div>

        {submitted && requiredMissing.length > 0 && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            Missing required fields: {requiredMissing.join(", ")}
          </div>
        )}

        {canProceed && (
          <div className="space-y-2 rounded border border-green-200 bg-green-50 p-3">
            <p className="text-sm text-green-800">
              Required fields are complete. Manual intake payload is ready.
            </p>
            <pre className="max-h-64 overflow-auto rounded bg-white p-2 text-xs text-gray-700">
              {JSON.stringify(payloadPreview, null, 2)}
            </pre>
            <p className="text-xs text-green-900">
              Note: this UI currently validates and formats manual intake data.
              Persisting these records requires a backend manual-ingest
              endpoint.
            </p>
          </div>
        )}
      </form>
    </div>
  );
}
