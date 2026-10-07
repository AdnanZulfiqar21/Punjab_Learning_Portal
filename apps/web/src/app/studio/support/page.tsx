import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { StaffSupportTicket } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { CATEGORY_LABEL, STATUS_LABEL, statusTone } from "@/app/help/status";
import { api } from "@/lib/session";
import { requireSupportStaff, StudioForbiddenError } from "@/lib/studio";

export const metadata: Metadata = { title: "Support queue", robots: { index: false } };

export default function SupportQueuePage({ searchParams }: PageProps<"/studio/support">) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Support queue</h1>
        <p className="text-muted">Learner requests. Reviewers see question reports in their subjects without the learner&apos;s identity.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading requests" />}>
        {searchParams.then((sp) => (
          <Queue status={typeof sp.status === "string" ? sp.status : ""} />
        ))}
      </Suspense>
    </div>
  );
}

async function Queue({ status }: { status: string }) {
  let token: string;
  try {
    ({ token } = await requireSupportStaff("/studio/support"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">Only support staff and subject reviewers can open the support queue.</Notice>;
    throw e;
  }
  const qs = STATUS_LABEL[status] ? `?status=${status}` : "";
  const res = await api<StaffSupportTicket[]>(`/v1/staff/support/tickets${qs}`, { token });
  if (!res.ok) return <Notice tone="warn" title="Couldn't load the queue">{res.problem?.detail ?? "Please try again."}</Notice>;
  return (
    <div className="space-y-3">
      <nav aria-label="Filter by status" className="flex flex-wrap gap-2 text-sm">
        {["", ...Object.keys(STATUS_LABEL)].map((s) => (
          <Link key={s || "all"} href={s ? `/studio/support?status=${s}` : "/studio/support"} aria-current={s === status ? "page" : undefined} className={`rounded-full border px-3 py-1 ${s === status ? "border-accent bg-accent-soft" : "border-border"}`}>
            {s ? STATUS_LABEL[s] : "All"}
          </Link>
        ))}
      </nav>
      {res.data.length === 0 ? (
        <Notice title="Nothing here">No requests match.</Notice>
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Support requests">
          {res.data.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div>
                <Link href={`/studio/support/${t.id}`} className="font-medium text-accent underline-offset-2 hover:underline">
                  {t.subject}
                </Link>
                <p className="text-sm text-muted">
                  {CATEGORY_LABEL[t.category]} · updated {new Date(t.updated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
                </p>
              </div>
              <Badge tone={statusTone(t.status)}>{STATUS_LABEL[t.status]}</Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
