"use server";

// P15.S3.T3: support staff find a learner by exact email (sent in the request body, never a URL), view a redacted
// timeline, and start or end time-limited assisted access. Learners can see and end assisted access themselves.
import { redirect } from "next/navigation";
import type { AssistedAccess, Problem, SupportLearner } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

const detail = (p: unknown, fallback: string) => (p as Problem | null)?.detail ?? fallback;

export type LookupState = { error?: string } | undefined;

export async function lookUpLearner(_prev: LookupState, form: FormData): Promise<LookupState> {
  const t = await token("/studio/support/learners");
  const email = String(form.get("email") ?? "").trim();
  if (!email) return { error: "Enter the learner's email address." };
  const res = await api<SupportLearner>("/v1/staff/support/learners/lookup", { method: "POST", token: t, body: JSON.stringify({ email }) });
  if (!res.ok) return { error: detail(res.problem, "Couldn't look that up.") };
  redirect(`/studio/support/learners/${res.data.id}`);
}

export async function startAssistedAccess(userId: string, ticketId: string, reason: string, minutes: number): Promise<{ ok: boolean; error?: string }> {
  const t = await token(`/studio/support/learners/${userId}`);
  const res = await api<AssistedAccess>(`/v1/staff/support/learners/${encodeURIComponent(userId)}/assisted-access`, {
    method: "POST",
    token: t,
    body: JSON.stringify({ ticket_id: ticketId, reason, minutes }),
  });
  if (res.ok) return { ok: true };
  const errs = (res.problem as (Problem & { errors?: { msg: string }[] }) | null)?.errors;
  return { ok: false, error: errs?.length ? errs.map((e) => e.msg).join(" ") : detail(res.problem, "Couldn't start assisted access.") };
}

export async function endAssistedAccess(accessId: string, asLearner: boolean): Promise<{ ok: boolean; error?: string }> {
  const t = await token(asLearner ? "/account" : "/studio/support");
  const path = asLearner ? `/v1/me/assisted-access/${encodeURIComponent(accessId)}` : `/v1/staff/support/assisted-access/${encodeURIComponent(accessId)}`;
  const res = await api<null>(path, { method: "DELETE", token: t });
  return res.ok ? { ok: true } : { ok: false, error: detail(res.problem, "Couldn't end assisted access.") };
}
