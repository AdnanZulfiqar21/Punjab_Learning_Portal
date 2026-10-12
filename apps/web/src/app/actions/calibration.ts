"use server";

// W06.S1.T3 (CALIBRATION-01): verdicts on calibration disagreements. The API checks the adjudicator's scope and MFA,
// that each disputed criterion has one verdict, and audits it; nothing here changes a mark.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type CalibrationResult = { ok: true } | { ok: false; error: string };

export async function adjudicateComparison(id: string, verdicts: Record<string, string>, reason: string): Promise<CalibrationResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/calibration");
  const res = await api<unknown>(`/v1/studio/written/calibration/${encodeURIComponent(id)}/adjudicate`, {
    method: "POST",
    token: t,
    body: JSON.stringify({ verdicts, reason }),
  });
  revalidatePath("/studio/calibration");
  if (res.ok) return { ok: true };
  return { ok: false, error: (res.problem as Problem | null)?.detail ?? `That didn't save (${res.status}).` };
}
