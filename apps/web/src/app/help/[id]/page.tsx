import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import type { SupportTicket } from "@portal/contracts";
import { IconTile, PageIcon } from "@/components/learner-pages";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { STATUS_LABEL, statusTone } from "../status";
import { ReplyBox } from "./reply-box";
import { AddScreenshot, ScreenshotList } from "./screenshots";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "Help request", robots: { index: false } };

export default function TicketPage({ params }: PageProps<"/help/[id]">) {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Breadcrumbs items={[{ href: "/help", label: "Help" }, { label: "Request" }]} />
      <Suspense fallback={<SkeletonLines lines={5} label="Loading your request" />}>
        {params.then(({ id }) => (
          <Ticket id={id} />
        ))}
      </Suspense>
    </div>
  );
}

async function Ticket({ id }: { id: string }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/help/${id}`);
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const res = await api<SupportTicket>(`/v1/support/tickets/${id}`, { token: user.token });
  if (!res.ok) notFound();
  const t = res.data;
  return (
    <div className="space-y-4">
      <div className="glass flex flex-wrap items-center justify-between gap-3 rounded-card px-6 py-5">
        <div className="flex min-w-0 items-center gap-3">
          <IconTile icon="message-circle" size={44} />
          <h1 className="min-w-0 font-display text-2xl font-bold tracking-tight break-words">{t.subject}</h1>
        </div>
        <Badge tone={statusTone(t.status)}>{STATUS_LABEL[t.status]}</Badge>
      </div>
      {/* Messages are reading text, so each sits on a solid surface (support replies tinted), never on glass. */}
      <ol className="space-y-3" aria-label="Conversation">
        {t.messages.map((m, i) => (
          <li
            key={i}
            className={`space-y-1.5 rounded-inner border px-4 py-3 ${m.from_staff ? "mr-0 border-accent/40 bg-accent-soft sm:mr-10" : "ml-0 border-border bg-surface sm:ml-10"}`}
          >
            <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
              <PageIcon name={m.from_staff ? "circle-help" : "user"} size={14} />
              {m.from_staff ? "Support team" : "You"} · {new Date(m.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE })}
            </p>
            <p className="whitespace-pre-line">{m.body}</p>
          </li>
        ))}
      </ol>
      {(t.corrections ?? []).map((c) => (
        <Notice key={c.id} tone="info" title={c.defect === "VOID" ? "The question was withdrawn after review" : "The question's answer was corrected after review"}>
          Recorded on {new Date(c.decided_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE })}. Affected results were re-scored as a new score version.
          {c.status === "superseded" && " A later decision replaced this one."}
        </Notice>
      ))}
      <ScreenshotList ticketId={t.id} shots={t.attachments ?? []} />
      {t.status !== "resolved" && <AddScreenshot ticketId={t.id} remaining={5 - (t.attachments?.length ?? 0)} />}
      <ReplyBox id={t.id} />
    </div>
  );
}
