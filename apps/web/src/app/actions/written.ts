"use server";

// Written-practice mutations through the BFF. The API enforces timing (U), revision concurrency, completeness and
// the one-receipt seal; these actions forward the learner's session and translate outcomes for the UI.
import { redirect } from "next/navigation";
import type { LinkedForm, Problem, WrittenAttempt, WrittenForm, WrittenSeal } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

export type WrittenBuilderState = { error?: string } | undefined;

/** W06.S2.T4: the learner confirms a seemingly blank answer was not attempted (resolved like a declared one). */
export async function confirmUnanswered(attemptId: string, position: number): Promise<{ ok: boolean; error?: string }> {
  const t = await token(`/practice/written/${attemptId}`);
  const res = await api<null>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/questions/${position}/confirm-unanswered`, {
    method: "POST",
    token: t,
  });
  return res.ok ? { ok: true } : { ok: false, error: (res.problem as Problem | null)?.detail ?? "Couldn't confirm." };
}

/**
 * W04.S3.T3: prepare a linked new practice test. Nothing is reserved yet; the confirmation page shows the allowance it
 * will use. The key comes from the panel, so a double click or retry returns the same prepared test.
 */
export async function prepareLinkedPractice(
  attemptId: string,
  key: string,
  reason: "REWRITE" | "NEW_CONTENT" | "INDETERMINATE",
  positions: number[],
  revisionId: string | null,
): Promise<{ error?: string }> {
  const t = await token(`/practice/written/${attemptId}`);
  const res = await api<LinkedForm>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/linked-forms`, {
    method: "POST",
    token: t,
    headers: { "Idempotency-Key": key },
    body: JSON.stringify({ reason, positions, revision_id: revisionId }),
  });
  if (!res.ok) return { error: (res.problem as Problem | null)?.detail ?? "Couldn't prepare the new practice test." };
  redirect(`/practice/written/linked/${res.data.form_id}`);
}

/** Starts a prepared linked test through the ordinary admission path (its own reservation). Idempotent per test. */
export async function startLinkedPractice(formId: string): Promise<void> {
  const t = await token(`/practice/written/linked/${formId}`);
  const attempt = await api<WrittenAttempt>(`/v1/written/forms/${encodeURIComponent(formId)}/attempt`, { method: "POST", token: t });
  if (!attempt.ok) redirect(`/practice/written/linked/${formId}?error=${attempt.status}`);
  redirect(`/practice/written/${attempt.data.id}`);
}

export async function createWrittenPractice(_prev: WrittenBuilderState, form: FormData): Promise<WrittenBuilderState> {
  const t = await token("/practice/written");
  const chapterIds = form.getAll("chapter_ids").map(String);
  if (chapterIds.length === 0) return { error: "Choose at least one chapter." };
  const timed = form.get("timed") === "on";
  const created = await api<WrittenForm>("/v1/written/forms", {
    method: "POST",
    token: t,
    headers: { "Idempotency-Key": String(form.get("idempotency_key") ?? "") },
    body: JSON.stringify({
      grade: Number(form.get("grade")),
      subject: String(form.get("subject") ?? ""),
      chapter_ids: chapterIds,
      question_type: String(form.get("question_type") ?? "mixed"),
      question_count: Number(form.get("question_count") ?? 1),
      writing_minutes: timed ? Number(form.get("writing_minutes") ?? 30) : null,
    }),
  });
  if (!created.ok) {
    if (created.status === 401) redirect("/signin?next=/practice/written");
    const p = created.problem as (Problem & { available?: number }) | null;
    return { error: `${p?.detail ?? "Could not create the test."}${p?.available !== undefined ? ` You can ask for up to ${p.available}.` : ""}` };
  }
  const attempt = await api<WrittenAttempt>(`/v1/written/forms/${created.data.id}/attempt`, { method: "POST", token: t });
  if (!attempt.ok) return { error: "The test was created but could not be started. Try again." };
  redirect(`/practice/written/${attempt.data.id}`);
}

export type ManifestOutcome =
  | { kind: "ok"; attempt: WrittenAttempt }
  | { kind: "conflict"; message: string }
  | { kind: "error"; message: string; errors?: string[] };

export async function saveMapping(
  attemptId: string,
  expectedRevision: number,
  slots: Record<string, { pages: string[]; unanswered: boolean }>,
): Promise<ManifestOutcome> {
  const t = await token(`/practice/written/${attemptId}`);
  const res = await api<WrittenAttempt>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/manifest`, {
    method: "PUT",
    token: t,
    body: JSON.stringify({ expected_revision: expectedRevision, slots }),
  });
  if (res.ok) return { kind: "ok", attempt: res.data };
  const p = res.problem as (Problem & { errors?: string[] }) | null;
  if (res.status === 409) return { kind: "conflict", message: p?.detail ?? "Your mapping changed elsewhere." };
  return { kind: "error", message: p?.detail ?? "Could not save the mapping.", errors: p?.errors };
}

export type SealOutcome = { kind: "ok"; seal: WrittenSeal } | { kind: "error"; message: string; missing?: string[] };

export async function sealScript(attemptId: string, idempotencyKey: string, expectedRevision: number): Promise<SealOutcome> {
  const t = await token(`/practice/written/${attemptId}`);
  try {
    const res = await api<WrittenSeal>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/seal`, {
      method: "POST",
      token: t,
      body: JSON.stringify({ idempotency_key: idempotencyKey, expected_revision: expectedRevision }),
    });
    if (res.ok) return { kind: "ok", seal: res.data };
    const p = res.problem as (Problem & { missing?: string[] }) | null;
    return { kind: "error", message: p?.detail ?? `Submission failed (${res.status}).`, missing: p?.missing };
  } catch {
    return { kind: "error", message: "Can't reach the service. Nothing was lost; submit again when you're back online." };
  }
}
