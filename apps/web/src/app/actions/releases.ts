"use server";

// P06.S3.T2 (CONTENT-RELEASE-01): publish several approved items together, or none of them, and roll a release back as a
// whole. The API checks the publisher's scope, MFA and independence and today's publication gate for every item.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type ReleaseProblem = { item_id: string; title: string; errors: string[] };
export type ReleaseResult = { ok: true } | { ok: false; error: string; items: ReleaseProblem[] };

function refused(status: number, problem: unknown): ReleaseResult {
  const p = problem as (Problem & { items?: ReleaseProblem[] }) | null;
  return { ok: false, error: p?.detail ?? `That didn't go through (${status}).`, items: p?.items ?? [] };
}

export async function publishRelease(itemIds: string[], label: string, reason: string): Promise<ReleaseResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/releases");
  const res = await api<unknown>("/v1/studio/releases", {
    method: "POST",
    token: t,
    body: JSON.stringify({ item_ids: itemIds, label, reason }),
  });
  revalidatePath("/studio/releases");
  return res.ok ? { ok: true } : refused(res.status, res.problem);
}

export async function rollBackRelease(id: string, reason: string): Promise<ReleaseResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/releases");
  const res = await api<unknown>(`/v1/studio/releases/${encodeURIComponent(id)}/rollback`, {
    method: "POST",
    token: t,
    body: JSON.stringify({ reason }),
  });
  revalidatePath("/studio/releases");
  return res.ok ? { ok: true } : refused(res.status, res.problem);
}
