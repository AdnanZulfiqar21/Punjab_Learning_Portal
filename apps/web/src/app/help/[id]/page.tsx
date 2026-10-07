import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import type { SupportTicket } from "@portal/contracts";
import { Badge, Breadcrumbs, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { STATUS_LABEL, statusTone } from "../status";
import { ReplyBox } from "./reply-box";

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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{t.subject}</h1>
        <Badge tone={statusTone(t.status)}>{STATUS_LABEL[t.status]}</Badge>
      </div>
      <ol className="space-y-3" aria-label="Conversation">
        {t.messages.map((m, i) => (
          <li key={i} className={`rounded-xl border p-3 ${m.from_staff ? "border-accent bg-accent-soft" : "border-border bg-surface"}`}>
            <p className="text-xs text-muted">
              {m.from_staff ? "Support team" : "You"} · {new Date(m.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
            </p>
            <p className="whitespace-pre-line">{m.body}</p>
          </li>
        ))}
      </ol>
      <ReplyBox id={t.id} />
    </div>
  );
}
