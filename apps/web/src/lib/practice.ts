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

/** P10.S4.T3 (EXAM-ROOM-01): while a mock runs, other tests and results are closed; this is the mock to go back to. */
export type MockRunning = { mockRunning: string };

function mockRunning(status: number, problem: unknown): MockRunning | null {
  const p = problem as (Problem & { code_reason?: string; attempt_id?: string }) | null;
  return status === 409 && p?.code_reason === "MOCK_IN_PROGRESS" && p.attempt_id ? { mockRunning: p.attempt_id } : null;
}

export async function getAttempt(token: string, id: string): Promise<PracticeAttempt | MockRunning | null> {
  const res = await api<PracticeAttempt>(`/v1/attempts/${encodeURIComponent(id)}`, { token });
  if (res.ok) return res.data;
  const running = mockRunning(res.status, res.problem);
  if (running) return running;
  if (res.status === 404 || res.status === 422) return null;
  throw new Error(res.problem?.detail ?? `Could not load the test (${res.status}).`);
}

export async function getResult(
  token: string,
  id: string,
): Promise<AttemptResult | "pending" | "scoring" | { heldUntil: string | null } | MockRunning | null> {
  const res = await api<AttemptResult>(`/v1/attempts/${encodeURIComponent(id)}/result`, { token });
  if (res.ok) return res.data;
  const running = mockRunning(res.status, res.problem);
  if (running) return running;
  const held = res.problem as (Problem & { code_reason?: string; available_at?: string | null }) | null;
  // A held scheduled mock (a missing release time means the session couldn't be resolved: still held, OCT9-01).
  if (res.status === 409 && held?.code_reason === "RESULTS_PENDING") return { heldUntil: held.available_at ?? null };
  if (res.status === 409 && held?.code_reason === "SCORING_PENDING") return "scoring"; // submitted; result being prepared
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
