import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { MarkingCaseSummary } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError, SUBJECT_LABEL } from "@/lib/studio";

export const metadata: Metadata = { title: "Written marking", robots: { index: false } };

export default function MarkingQueuePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Written marking</h1>
        <p className="text-muted">Submitted answer scripts in your subjects. Learner names are not shown to markers.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading scripts" />}>
        <Queue />
      </Suspense>
    </div>
  );
}

async function Queue() {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio/marking"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const res = await api<MarkingCaseSummary[]>("/v1/studio/written/queue", { token });
  if (!res.ok) {
    return <Notice tone="warn" title="Reviewers only">Only subject reviewers can mark written scripts.</Notice>;
  }
  if (res.data.length === 0) return <Notice title="Nothing to mark">No submitted scripts are waiting in your subjects.</Notice>;
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Scripts awaiting marking">
      {res.data.map((c) => (
        <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <Link href={`/studio/marking/${c.id}`} className="font-medium text-accent underline-offset-2 hover:underline">
              Script {c.reference}
            </Link>
            <p className="text-sm text-muted">
              {GRADE_LABEL[c.grade]} {SUBJECT_LABEL[c.subject] ?? c.subject} · submitted {new Date(c.opened_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
            </p>
          </div>
          <div className="flex gap-2">
            <Badge>{c.case_kind === "recheck" ? "Recheck" : c.case_kind === "completion" ? "Completion" : "First marking"}</Badge>
            {c.leased_by_me && <Badge tone="ok">You are marking</Badge>}
            {c.leased_by_other && <Badge tone="warn">Another teacher is marking</Badge>}
          </div>
        </li>
      ))}
    </ul>
  );
}
