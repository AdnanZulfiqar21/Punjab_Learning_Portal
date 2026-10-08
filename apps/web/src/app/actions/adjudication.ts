"use server";

// W06.S2.T3: academic adjudicators apply a published rubric correction to earlier work and run the bounded regrade.
// The API enforces scope, the compatible-denominator rule, explicit superseding and idempotent per-attempt regrades.
import { redirect } from "next/navigation";
import type { Adjudication, Problem, RegradeRun } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

export type AdjudicationFormState = { error?: string; active?: string[] } | undefined;

export async function createAdjudication(_prev: AdjudicationFormState, form: FormData): Promise<AdjudicationFormState> {
  const rubric = String(form.get("rubric_item_id") ?? "");
  const t = await token(`/studio/adjudications/new?rubric=${rubric}`);
  const supersedes = String(form.get("supersedes_id") ?? "");
  const res = await api<Adjudication>("/v1/studio/written/adjudications", {
    method: "POST",
    token: t,
    body: JSON.stringify({ rubric_item_id: rubric, reason: String(form.get("reason") ?? ""), supersedes_id: supersedes || null }),
  });
  if (!res.ok) {
    const p = res.problem as (Problem & { active?: string[] }) | null;
    return { error: p?.detail ?? `Request failed (${res.status}).`, active: p?.active };
  }
  redirect(`/studio/adjudications/${res.data.id}`);
}

export async function runRegrade(id: string): Promise<{ ok: true; run: RegradeRun } | { ok: false; error: string }> {
  const t = await token(`/studio/adjudications/${id}`);
  const res = await api<RegradeRun>(`/v1/studio/written/adjudications/${encodeURIComponent(id)}/run?limit=50`, { method: "POST", token: t });
  if (res.ok) return { ok: true, run: res.data };
  return { ok: false, error: (res.problem as Problem | null)?.detail ?? `Request failed (${res.status}).` };
}
