// Server-only helpers for written practice. Scripts are private learner evidence: always fetched with the learner's
// session and never cached. Rubrics are never sent to learners.
import type { WrittenAttempt, WrittenAvailability } from "@portal/contracts";
import { api } from "@/lib/session";

export async function getWrittenAvailability(token: string, grade: number, subject: string): Promise<WrittenAvailability | null> {
  const res = await api<WrittenAvailability>(`/v1/written/availability?grade=${grade}&subject=${encodeURIComponent(subject)}`, { token });
  if (res.ok) return res.data;
  if (res.status === 404) return null;
  throw new Error(res.problem?.detail ?? `Could not load written practice (${res.status}).`);
}

export async function getWrittenAttempt(token: string, id: string): Promise<WrittenAttempt | null> {
  const res = await api<WrittenAttempt>(`/v1/written-attempts/${encodeURIComponent(id)}`, { token });
  if (res.ok) return res.data;
  if (res.status === 404 || res.status === 422) return null;
  throw new Error(res.problem?.detail ?? `Could not load the answer script (${res.status}).`);
}

export const marks = (units: number) => {
  const m = units / 100;
  return Number.isInteger(m) ? String(m) : m.toFixed(2).replace(/0$/, "");
};
