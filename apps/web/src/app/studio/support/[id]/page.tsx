import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { StaffSupportTicket } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { CATEGORY_LABEL, STATUS_LABEL, statusTone } from "@/app/help/status";
import { api } from "@/lib/session";
import { requireSupportStaff, StudioForbiddenError } from "@/lib/studio";
import { StaffReplyBox } from "./staff-reply-box";

export const metadata: Metadata = { title: "Support request", robots: { index: false } };

export default function StaffTicketPage({ params }: PageProps<"/studio/support/[id]">) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Breadcrumbs items={[{ href: "/studio/support", label: "Support queue" }, { label: "Request" }]} />
      <Suspense fallback={<SkeletonLines lines={6} label="Loading the request" />}>
        {params.then(({ id }) => (
          <Ticket id={id} />
        ))}
      </Suspense>
    </div>
  );
}

type Context = {
  learner: { email: string | null } | null;
  plan: { trial: string; trial_ends_at: string | null; has_access: boolean } | null;
  question: { item_id: string; title: string; kind: string; version: number; availability: string; quarantine_level: string | null } | null;
};

const date = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

async function Ticket({ id }: { id: string }) {
  let token: string;
  try {
    ({ token } = await requireSupportStaff(`/studio/support/${id}`));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">Only support staff and subject reviewers can open support requests.</Notice>;
    throw e;
  }
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const res = await api<StaffSupportTicket>(`/v1/staff/support/tickets/${id}`, { token });
  if (!res.ok) notFound();
  const t = res.data;
  const ctx = t.context as Context;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t.subject}</h1>
          <p className="text-sm text-muted">
            {CATEGORY_LABEL[t.category]} · opened {date(t.created_at)}
          </p>
        </div>
        <Badge tone={statusTone(t.status)}>{STATUS_LABEL[t.status]}</Badge>
      </div>
      <section aria-labelledby="ctx-h" className="space-y-1 rounded-xl border border-border bg-surface-muted p-4 text-sm">
        <h2 id="ctx-h" className="font-semibold">
          Context
        </h2>
        {ctx.learner && <p>Learner: {ctx.learner.email ?? "no email on file"}</p>}
        {ctx.plan && (
          <p>
            Trial: {ctx.plan.trial}
            {ctx.plan.trial_ends_at && <> (ends {date(ctx.plan.trial_ends_at)})</>} · {ctx.plan.has_access ? "has access" : "no active access"}
          </p>
        )}
        {ctx.question && (
          <p>
            Question:{" "}
            <Link href={`/studio/items/${ctx.question.item_id}`} className="text-accent underline underline-offset-2">
              {ctx.question.title}
            </Link>{" "}
            · version {ctx.question.version} · {ctx.question.availability}
            {ctx.question.quarantine_level && <> · quarantine {ctx.question.quarantine_level}</>}
          </p>
        )}
        {!ctx.learner && !ctx.question && <p className="text-muted">No extra context.</p>}
        {!ctx.learner && ctx.question && <p className="text-muted">The learner&apos;s identity is not shown to reviewers.</p>}
      </section>
      <ol className="space-y-3" aria-label="Conversation">
        {t.messages.map((m, i) => (
          <li key={i} className={`rounded-xl border p-3 ${m.internal ? "border-warn bg-warn-soft" : m.from_staff ? "border-accent bg-accent-soft" : "border-border bg-surface"}`}>
            <p className="text-xs text-muted">
              {m.internal ? "Internal note" : m.from_staff ? "Staff reply" : "Learner"} · {date(m.created_at)}
            </p>
            <p className="whitespace-pre-line">{m.body}</p>
          </li>
        ))}
      </ol>
      <StaffReplyBox id={t.id} status={t.status} />
    </div>
  );
}
