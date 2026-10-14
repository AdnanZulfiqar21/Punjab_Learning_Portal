import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { AcademicReview, Adjudication } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError, SUBJECT_LABEL } from "@/lib/studio";
import { TIME_ZONE } from "@/lib/dates";
import { ResolveForm } from "./resolve-form";

export const metadata: Metadata = { title: "Academic reviews", robots: { index: false } };

const KIND: Record<string, string> = {
  unlisted_method: "Valid method the guide doesn't list",
  rubric_defect: "Problem with the marking guide",
};
const OUTCOME: Record<string, string> = {
  guide_corrected: "Guide corrected to cover it",
  not_covered: "Guide stands",
};
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });

// ACADEMIC-REVIEW-01 (W01.S2.T2, W05.S2.T3): questions a teacher kept pending because the marking guide doesn't
// cover the learner's method. Nobody can mark them until an academic adjudicator decides how the guide applies.
export default function AcademicReviewsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Academic reviews</h1>
        <p className="text-muted">
          Questions a teacher kept pending because the marking guide doesn&apos;t cover the learner&apos;s method. They can&apos;t be marked until you
          decide how the guide applies. To cover a method, publish a corrected guide and approve the correction first, then name it here.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading academic reviews" />}>
        <List />
      </Suspense>
    </div>
  );
}

async function List() {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio/academic-reviews"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const [open, resolved, corrections] = await Promise.all([
    api<AcademicReview[]>("/v1/studio/written/academic-reviews", { token }),
    api<AcademicReview[]>("/v1/studio/written/academic-reviews?status=resolved", { token }),
    api<Adjudication[]>("/v1/studio/written/adjudications?limit=100", { token }),
  ]);
  if (!open.ok) return <Notice tone="warn" title="Academic staff only">Only academic staff in these subjects can see academic reviews.</Notice>;
  const active = corrections.ok ? corrections.data.filter((a) => a.status === "active") : [];
  return (
    <div className="space-y-8">
      <section aria-labelledby="open-h" className="space-y-3">
        <h2 id="open-h" className="text-lg font-semibold">
          Waiting for a decision
        </h2>
        {open.data.length === 0 ? (
          <Notice title="Nothing waiting">No question in your subjects is waiting for academic review.</Notice>
        ) : (
          <ul className="space-y-4" aria-label="Open academic reviews">
            {open.data.map((r) => (
              <li key={r.id} className="space-y-3 rounded-xl border border-border bg-surface p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    Script {r.reference} · question {r.position} · {GRADE_LABEL[r.grade]} {SUBJECT_LABEL[r.subject] ?? r.subject}
                  </p>
                  <Badge tone="warn">{KIND[r.kind] ?? r.kind}</Badge>
                </div>
                <p className="text-sm">
                  <span className="font-medium">Teacher&apos;s note:</span> {r.reason}
                </p>
                <p className="text-sm text-muted">
                  Raised {when(r.raised_at)}
                  {r.rubric_version ? ` · marking guide version ${r.rubric_version}` : ""}
                  {r.rubric_item_id && (
                    <>
                      {" · "}
                      <Link href={`/studio/items/${r.rubric_item_id}`} className="text-accent underline underline-offset-2">
                        Open the marking guide
                      </Link>
                    </>
                  )}
                </p>
                <ResolveForm
                  reviewId={r.id}
                  corrections={active
                    .filter((a) => a.rubric_item_id === r.rubric_item_id)
                    .map((a) => ({ id: a.id, label: `Approved ${when(a.approved_at)}: ${a.reason}` }))}
                />
              </li>
            ))}
          </ul>
        )}
      </section>
      {resolved.ok && resolved.data.length > 0 && (
        <section aria-labelledby="done-h" className="space-y-3">
          <h2 id="done-h" className="text-lg font-semibold">
            Decided
          </h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Decided academic reviews">
            {resolved.data.map((r) => (
              <li key={r.id} className="px-4 py-3 text-sm">
                <p className="font-medium">
                  Script {r.reference} · question {r.position} · {OUTCOME[r.resolution ?? ""] ?? r.resolution}
                </p>
                <p className="text-muted">
                  {r.resolution_note}
                  {r.resolved_at ? ` · ${when(r.resolved_at)}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
