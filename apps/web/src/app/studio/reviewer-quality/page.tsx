import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { ReviewerQuality } from "@portal/contracts";
import { Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError, SUBJECT_LABEL } from "@/lib/studio";

export const metadata: Metadata = { title: "Reviewer quality", robots: { index: false } };

const scopeLabel = (s: string) => {
  const [grade, subject] = s.split(":");
  return `${GRADE_LABEL[Number(grade)] ?? grade} ${SUBJECT_LABEL[subject] ?? subject}`;
};

// REVIEWER-QUALITY-01 (W06.S3.T3, part): raw counts for academic leads. No threshold here judges a marker; a handful of
// rechecks says little, and what counts as a concerning rate is the academic lead's decision.
export default function ReviewerQualityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Reviewer quality</h1>
        <p className="text-muted">
          For each marker in your subjects over the last 90 days: decisions released, how many a learner asked to recheck, whether another
          teacher changed or upheld the marks, how often a marking-guide correction sent their work back to a teacher, and the methods they sent
          to{" "}
          <Link href="/studio/academic-reviews" className="text-accent underline underline-offset-2">
            academic review
          </Link>
          . These are counts, not verdicts.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading reviewer figures" />}>
        <Table />
      </Suspense>
    </div>
  );
}

async function Table() {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio/reviewer-quality"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const res = await api<ReviewerQuality[]>("/v1/studio/written/reviewer-quality", { token });
  if (!res.ok) return <Notice tone="warn" title="Academic adjudicators only">Only academic adjudicators can see reviewer figures.</Notice>;
  if (res.data.length === 0) return <Notice title="Nothing yet">No teacher has released marks in your subjects in the last 90 days.</Notice>;
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <caption className="sr-only">Per-marker figures for the last 90 days</caption>
        <thead className="text-left text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Marker</th>
            <th scope="col" className="px-3 py-2 font-medium">Subjects</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Decisions</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Rechecked</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Changed</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Upheld</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Re-marked after a guide correction</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Sent to academic review</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {res.data.map((r) => (
            <tr key={r.reviewer_id}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                {r.reviewer}
              </th>
              <td className="px-3 py-2">{r.scopes.map(scopeLabel).join(", ")}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.decisions}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.rechecked}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.changed_on_recheck}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.upheld_on_recheck}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.teacher_regrades}</td>
              <td className="px-3 py-2 text-right tabular-nums">{r.academic_reviews_raised}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
