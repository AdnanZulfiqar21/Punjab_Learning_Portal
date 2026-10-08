"use server";

// Teacher marking actions. The API enforces scope, the lease, expected-version CAS and rubric-bound awards.
import { redirect } from "next/navigation";
import type { MarkingCase, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/marking");
  return t;
}

export type MarkingOutcome = { ok: true; case: MarkingCase } | { ok: false; error: string; errors?: string[]; conflict?: boolean };

async function call(path: string, body?: unknown): Promise<MarkingOutcome> {
  const res = await api<MarkingCase>(path, { method: "POST", token: await token(), body: JSON.stringify(body ?? {}) });
  if (res.ok) return { ok: true, case: res.data };
  const p = res.problem as (Problem & { errors?: string[] }) | null;
  return { ok: false, error: p?.detail ?? `Request failed (${res.status}).`, errors: p?.errors, conflict: res.status === 409 };
}

export async function takeLease(caseId: string): Promise<MarkingOutcome> {
  return call(`/v1/studio/written/cases/${encodeURIComponent(caseId)}/lease`);
}

export async function saveMarks(
  caseId: string,
  expectedVersion: number,
  awards: Record<string, Record<string, { units: number; reason: string }>>,
  release: boolean,
  expansion?: { positions: number[]; reason: string },
): Promise<MarkingOutcome> {
  return call(`/v1/studio/written/cases/${encodeURIComponent(caseId)}/decision`, {
    expected_version: expectedVersion,
    awards,
    release,
    reason: release ? "Released by the marking teacher" : "Saved by the marking teacher",
    expand_positions: expansion?.positions ?? [],
    expansion_reason: expansion?.reason ?? "",
  });
}
