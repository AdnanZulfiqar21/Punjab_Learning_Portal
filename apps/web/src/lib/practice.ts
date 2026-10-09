// Server-only practice helpers. Attempts are private learner data: always fetched with the learner's session, never
// cached. Keys and explanations only ever arrive in results after submission (or a deliberate immediate-feedback check).
import type { AttemptResult, PracticeAttempt, PracticeAvailability, Problem } from "@portal/contracts";
import { api } from "@/lib/session";

export async function getAvailability(token: string, grade: number, subject: string): Promise<PracticeAvailability | null> {
  const res = await api<PracticeAvailability>(`/v1/practice/availability?grade=${grade}&subject=${encodeURIComponent(subject)}`, {
    token,
  });
  if (res.ok) return res.data;
  if (res.status === 404) return null;
  throw new Error(res.problem?.detail ?? `Could not load practice availability (${res.status}).`);
}

export async function getAttempt(token: string, id: string): Promise<PracticeAttempt | null> {
  const res = await api<PracticeAttempt>(`/v1/attempts/${encodeURIComponent(id)}`, { token });
  if (res.ok) return res.data;
  if (res.status === 404 || res.status === 422) return null;
  throw new Error(res.problem?.detail ?? `Could not load the test (${res.status}).`);
}

export async function getResult(token: string, id: string): Promise<AttemptResult | "pending" | { heldUntil: string } | null> {
  const res = await api<AttemptResult>(`/v1/attempts/${encodeURIComponent(id)}/result`, { token });
  if (res.ok) return res.data;
  const held = res.problem as (Problem & { code_reason?: string; available_at?: string }) | null;
  if (res.status === 409 && held?.code_reason === "RESULTS_PENDING" && held.available_at) return { heldUntil: held.available_at };
  if (res.status === 409) return "pending";
  if (res.status === 404 || res.status === 422) return null;
  throw new Error(res.problem?.detail ?? `Could not load the result (${res.status}).`);
}

export const SUBJECTS: [string, string][] = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
];
