"use server";

// W06.S2.T3: academic adjudicators (MFA session) apply a published rubric correction to earlier work. Applying only
// queues a durable job; a separate worker processes it in bounded batches and the page polls the job's progress.
// The API enforces scope, MFA, the compatible-denominator rule, explicit superseding and idempotent per-script work.
import { redirect } from "next/navigation";
import type { Adjudication, Problem, RegradeJob } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

const detail = (p: unknown, status: number) => (p as Problem | null)?.detail ?? `Request failed (${status}).`;

export type AdjudicationFormState = { error?: string; active?: string[] } | undefined;

export async function createAdjudication(_prev: AdjudicationFormState, form: FormData): Promise<AdjudicationFormState> {
  const rubric = String(form.get("rubric_item_id") ?? "");
  const t = await token(`/studio/adjudications/new?rubric=${rubric}`);
  const from = form.getAll("from_version_ids").map(String);
  if (from.length === 0) return { error: "Choose at least one earlier version to correct." };
  const res = await api<Adjudication>("/v1/studio/written/adjudications", {
    method: "POST",
    token: t,
    body: JSON.stringify({
      rubric_item_id: rubric,
      reason: String(form.get("reason") ?? ""),
      from_version_ids: from,
      supersedes_ids: form.getAll("supersedes_ids").map(String),
    }),
  });
  if (!res.ok) {
    const p = res.problem as (Problem & { active?: string[] }) | null;
    return { error: detail(p, res.status), active: p?.active };
  }
  redirect(`/studio/adjudications/${res.data.id}`);
}

type JobOutcome = { ok: true; job: RegradeJob } | { ok: false; error: string };

export async function queueRegrade(id: string): Promise<JobOutcome> {
  const t = await token(`/studio/adjudications/${id}`);
  const res = await api<RegradeJob>(`/v1/studio/written/adjudications/${encodeURIComponent(id)}/run`, { method: "POST", token: t });
  return res.ok ? { ok: true, job: res.data } : { ok: false, error: detail(res.problem, res.status) };
}

export async function regradeJob(jobId: string): Promise<JobOutcome> {
  const t = await token("/studio/adjudications");
  const res = await api<RegradeJob>(`/v1/studio/written/regrade-jobs/${encodeURIComponent(jobId)}`, { token: t });
  return res.ok ? { ok: true, job: res.data } : { ok: false, error: detail(res.problem, res.status) };
}

export async function retryRegrade(jobId: string): Promise<JobOutcome> {
  const t = await token("/studio/adjudications");
  const res = await api<RegradeJob>(`/v1/studio/written/regrade-jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST", token: t });
  return res.ok ? { ok: true, job: res.data } : { ok: false, error: detail(res.problem, res.status) };
}
