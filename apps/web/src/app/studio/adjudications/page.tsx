import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { Adjudication } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError, SUBJECT_LABEL } from "@/lib/studio";

export const metadata: Metadata = { title: "Rubric corrections", robots: { index: false } };

export default function AdjudicationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Rubric corrections</h1>
        <p className="text-muted">
          Published rubric corrections applied to work already started or marked. Start one from the corrected rubric&apos;s page.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading corrections" />}>
        <List />
      </Suspense>
    </div>
  );
}

async function List() {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio/adjudications"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const res = await api<Adjudication[]>("/v1/studio/written/adjudications", { token });
  if (!res.ok) return <Notice tone="warn" title="Reviewers only">Only academic staff can see rubric corrections.</Notice>;
  if (res.data.length === 0) return <Notice title="None yet">No rubric corrections have been applied in your subjects.</Notice>;
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Rubric corrections">
      {res.data.map((a) => (
        <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <Link href={`/studio/adjudications/${a.id}`} className="font-medium text-accent underline-offset-2 hover:underline">
              {GRADE_LABEL[a.grade]} {SUBJECT_LABEL[a.subject] ?? a.subject} · {new Date(a.approved_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
            </Link>
            <p className="text-sm text-muted">{a.reason}</p>
          </div>
          <div className="flex gap-2">
            <Badge tone={a.status === "active" ? "ok" : "info"}>{a.status === "active" ? "Active" : "Superseded"}</Badge>
            {a.latest_job ? (
              <Badge tone={a.latest_job.status === "failed" ? "warn" : "info"}>
                Last run: {a.latest_job.status} · {a.latest_job.processed} processed · {a.latest_job.failed} failed
              </Badge>
            ) : (
              <Badge>Not applied yet</Badge>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
