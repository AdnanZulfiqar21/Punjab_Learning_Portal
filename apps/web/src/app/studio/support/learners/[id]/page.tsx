import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { LearnerTimeline } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { requireSupportStaff, StudioForbiddenError } from "@/lib/studio";
import { AssistPanel } from "./assist-panel";

export const metadata: Metadata = { title: "Learner activity", robots: { index: false } };

export default function LearnerPage({ params }: PageProps<"/studio/support/learners/[id]">) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Breadcrumbs
        items={[
          { href: "/studio/support", label: "Support queue" },
          { href: "/studio/support/learners", label: "Find a learner" },
          { label: "Activity" },
        ]}
      />
      <Suspense fallback={<SkeletonLines lines={8} label="Loading the learner's activity" />}>
        {params.then(({ id }) => (
          <Timeline id={id} />
        ))}
      </Suspense>
    </div>
  );
}

const date = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

const KIND_LABEL: Record<string, string> = {
  "account.created": "Account created",
  "trial.granted": "Free trial started",
  "trial.claim": "Trial decision",
  "trial.device_authorized": "Trial device approved",
  "trial.device_removed": "Trial device removed",
  "trial.exception": "Trial exception granted",
  "access.granted": "Access granted",
  "access.revoked": "Access revoked",
  "access.refunded": "Access refunded",
  "practice.started": "Practice test started",
  "practice.finished": "Practice test finished",
  "written.started": "Written test started",
  "written.submitted": "Written test submitted",
  "written.expired": "Written test expired",
  "support.opened": "Help request opened",
};

function describe(detail: Record<string, unknown>): string {
  return Object.entries(detail)
    .filter(([k, v]) => v !== null && v !== undefined && !k.endsWith("_id"))
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

async function Timeline({ id }: { id: string }) {
  let staff: { token: string; isSupport: boolean } | null = null;
  try {
    staff = await requireSupportStaff(`/studio/support/learners/${id}`);
  } catch (e) {
    if (!(e instanceof StudioForbiddenError)) throw e;
  }
  if (!staff?.isSupport) return <Notice tone="warn" title="Support staff only">Only support staff can view learner activity.</Notice>;
  const { token } = staff;
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const res = await api<LearnerTimeline>(`/v1/staff/support/learners/${id}/timeline`, { token });
  if (!res.ok && res.status === 403) return <Notice tone="warn" title="Multi-factor sign-in needed">{res.problem?.detail ?? "Sign in again with MFA to view learner activity."}</Notice>;
  if (!res.ok) notFound();
  const { learner, assisted_access: assist, events } = res.data;
  const openRequests = events
    .filter((e) => e.kind === "support.opened" && e.detail.status !== "resolved")
    .map((e) => ({ id: String(e.detail.ticket_id), label: `${String(e.detail.category)} request from ${date(e.at)}` }));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{learner.email ?? "Learner without an email"}</h1>
          <p className="text-sm text-muted">
            Joined {date(learner.created_at)} · {learner.open_requests} open request{learner.open_requests === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex gap-2">
          {learner.status !== "active" && <Badge tone="warn">{learner.status}</Badge>}
          {assist && <Badge tone="warn">Assisted access until {date(assist.expires_at)}</Badge>}
        </div>
      </div>
      <AssistPanel userId={learner.id} active={assist ? { id: assist.id, expiresAt: assist.expires_at } : null} openRequests={openRequests} />
      <section aria-labelledby="tl-h" className="space-y-2">
        <h2 id="tl-h" className="font-semibold">
          Activity (newest first)
        </h2>
        <p className="text-sm text-muted">Answers, uploads, message text and device identifiers are never shown here.{assist ? " Result summaries are shown while assisted access lasts." : ""}</p>
        <ol className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Activity">
          {events.map((e, i) => (
            <li key={i} className="space-y-0.5 p-3 text-sm">
              <p>
                <span className="font-medium">{KIND_LABEL[e.kind] ?? e.kind}</span> <span className="text-muted">· {date(e.at)}</span>
              </p>
              {Object.keys(e.detail).length > 0 && <p className="text-muted">{describe(e.detail)}</p>}
              {e.kind === "support.opened" && typeof e.detail.ticket_id === "string" && (
                <Link href={`/studio/support/${e.detail.ticket_id}`} className="text-accent underline underline-offset-2">
                  Open request
                </Link>
              )}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
