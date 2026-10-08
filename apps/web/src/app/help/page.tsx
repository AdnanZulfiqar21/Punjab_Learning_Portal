import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { SupportTicket } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { STATUS_LABEL, statusTone } from "./status";

export const metadata: Metadata = { title: "Help", robots: { index: false } };

export default function HelpPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Help</h1>
          <p className="text-muted">Ask about your account, plan or a technical problem. To report a mistake in a question, use the link under it in your results.</p>
        </div>
        <Link href="/help/new" className="rounded-lg bg-accent px-4 py-2.5 font-medium text-white hover:bg-accent-strong dark:text-background">
          New request
        </Link>
      </div>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading your requests" />}>
        <Tickets />
      </Suspense>
    </div>
  );
}

async function Tickets() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/help");
  const res = await api<SupportTicket[]>("/v1/support/tickets", { token: user.token });
  const tickets = res.ok ? res.data : [];
  if (tickets.length === 0) return <Notice title="No requests yet">When you ask for help, your requests and our replies appear here.</Notice>;
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Your requests">
      {tickets.map((t) => (
        <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link href={`/help/${t.id}`} className="font-medium text-accent underline-offset-2 hover:underline">
            {t.subject}
          </Link>
          <Badge tone={statusTone(t.status)}>{STATUS_LABEL[t.status]}</Badge>
        </li>
      ))}
    </ul>
  );
}
