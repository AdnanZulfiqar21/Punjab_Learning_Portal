"use server";

// Practice mutations through the BFF. The API applies the §10.5 protocol; these actions only forward the learner's
// session and translate outcomes for the UI. A failed network call is never reported as saved.
import { redirect } from "next/navigation";
import type { AnswerOpResult, PracticeAttempt, PracticeForm, Problem, RevealResult, SubmitResult } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

export type BuilderState = { error?: string; available?: number } | undefined;

export async function createPractice(_prev: BuilderState, form: FormData): Promise<BuilderState> {
  const t = await token("/practice");
  const scope = String(form.get("scope") ?? "chapters");
  const chapterIds = scope === "chapters" ? form.getAll("chapter_ids").map(String) : [];
  if (scope === "chapters" && chapterIds.length === 0) return { error: "Choose at least one chapter." };
  const timed = form.get("timed") === "on";
  const body = {
    grade: Number(form.get("grade")),
    subject: String(form.get("subject") ?? ""),
    scope,
    half: form.get("half") ? Number(form.get("half")) : null,
    chapter_ids: chapterIds,
    question_count: Number(form.get("question_count") ?? 10),
    timed_minutes: timed ? Number(form.get("timed_minutes") ?? 10) : null,
    feedback_mode: form.get("feedback_mode") === "immediate" ? "immediate" : "deferred",
  };
  const created = await api<PracticeForm>("/v1/practice/forms", {
    method: "POST",
    token: t,
    body: JSON.stringify(body),
    headers: { "Idempotency-Key": String(form.get("idempotency_key") ?? "") },
  });
  if (!created.ok) {
    if (created.status === 401) redirect("/signin?next=/practice");
    const p = created.problem as (Problem & { available?: number }) | null;
    return { error: p?.detail ?? "Could not create the test.", available: p?.available };
  }
  const attempt = await api<PracticeAttempt>(`/v1/practice/forms/${created.data.id}/attempt`, { method: "POST", token: t });
  if (!attempt.ok) return { error: (attempt.problem as Problem | null)?.detail ?? "The test was created but could not be started. Try again." };
  redirect(`/practice/attempt/${attempt.data.id}`);
}

export type Op = { op_id: string; position: number; revision: number; option_id: string | null };

export type SaveOutcome =
  | { kind: "ok"; status: string; results: AnswerOpResult[] }
  | { kind: "finalised"; results: AnswerOpResult[] }
  | { kind: "error"; message: string };

export async function saveAnswers(attemptId: string, ops: Op[]): Promise<SaveOutcome> {
  const t = await token(`/practice/attempt/${attemptId}`);
  try {
    const res = await api<{ status: string; results: AnswerOpResult[] }>(`/v1/attempts/${encodeURIComponent(attemptId)}/answers`, {
      method: "POST",
      token: t,
      body: JSON.stringify({ ops }),
    });
    if (res.ok) return { kind: "ok", status: res.data.status, results: res.data.results };
    if (res.status === 409) {
      const p = res.problem as (Problem & { results?: AnswerOpResult[] }) | null;
      return { kind: "finalised", results: p?.results ?? [] };
    }
    return { kind: "error", message: res.problem?.detail ?? `Save failed (${res.status}).` };
  } catch {
    return { kind: "error", message: "Can't reach the service. Your answers are kept on this device and will be sent again." };
  }
}

export type SubmitOutcome = { kind: "ok"; result: SubmitResult } | { kind: "error"; message: string };

export async function submitAttempt(attemptId: string, idempotencyKey: string, ops: Op[]): Promise<SubmitOutcome> {
  const t = await token(`/practice/attempt/${attemptId}`);
  try {
    const res = await api<SubmitResult>(`/v1/attempts/${encodeURIComponent(attemptId)}/submit`, {
      method: "POST",
      token: t,
      body: JSON.stringify({ idempotency_key: idempotencyKey, ops }),
    });
    if (res.ok) return { kind: "ok", result: res.data };
    return { kind: "error", message: res.problem?.detail ?? `Submission failed (${res.status}).` };
  } catch {
    return { kind: "error", message: "Can't reach the service. Nothing was lost; submit again when you're back online." };
  }
}

export async function revealItem(attemptId: string, position: number): Promise<{ ok: true; data: RevealResult } | { ok: false; message: string }> {
  const t = await token(`/practice/attempt/${attemptId}`);
  const res = await api<RevealResult>(`/v1/attempts/${encodeURIComponent(attemptId)}/items/${position}/reveal`, {
    method: "POST",
    token: t,
  });
  return res.ok ? { ok: true, data: res.data } : { ok: false, message: res.problem?.detail ?? "Could not check this answer." };
}
