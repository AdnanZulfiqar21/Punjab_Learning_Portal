"use server";

// ACADEMIC-REVIEW-01: an academic adjudicator (MFA session) decides how the marking guide applies to a method a
// teacher found it doesn't cover. Resolving never sets a mark; the question is then marked as usual.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { AcademicReview, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type ResolveState = { error?: string; done?: boolean } | undefined;

export async function resolveAcademicReview(_prev: ResolveState, form: FormData): Promise<ResolveState> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/academic-reviews");
  const id = String(form.get("review_id") ?? "");
  const resolution = String(form.get("resolution") ?? "");
  const adjudication = String(form.get("adjudication_id") ?? "");
  const res = await api<AcademicReview>(`/v1/studio/written/academic-reviews/${encodeURIComponent(id)}/resolve`, {
    method: "POST",
    token: t,
    body: JSON.stringify({
      resolution,
      note: String(form.get("note") ?? ""),
      adjudication_id: resolution === "guide_corrected" && adjudication ? adjudication : null,
    }),
  });
  if (!res.ok) return { error: (res.problem as Problem | null)?.detail ?? `Request failed (${res.status}).` };
  revalidatePath("/studio/academic-reviews");
  return { done: true };
}
