import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { SupportTicket } from "@portal/contracts";
import { ButtonLink } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { IconTile, PageIcon } from "@/components/learner-pages";
import { PageHero } from "@/components/page-hero";
import { SectionHeader } from "@/components/section-header";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { STATUS_LABEL, statusTone } from "./status";

export const metadata: Metadata = { title: "Help", robots: { index: false } };

export default function HelpPage() {
  return (
    <div className="space-y-8">
      <PageHero
        eyebrow="Help"
        title="Help"
        lead="Ask about your account, plan or a technical problem. To report a mistake in a question, use the link under it in your results."
        actions={
          <>
            <ButtonLink href="/help/new" size="lg">
              <PageIcon name="plus" size={18} />
              New request
            </ButtonLink>
            <ButtonLink href="/help/articles" variant="secondary" size="lg">
              <Icon name="book-open" size={18} />
              Browse help articles
            </ButtonLink>
          </>
        }
      />
      <section aria-labelledby="requests-heading" className="mx-auto max-w-3xl">
        <SectionHeader id="requests-heading" title="Your requests" />
        <Suspense fallback={<SkeletonLines lines={4} label="Loading your requests" />}>
          <Tickets />
        </Suspense>
      </section>
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
    <ul className="space-y-3" aria-label="Your requests">
      {tickets.map((t) => (
        <GlassCard as="li" key={t.id} interactive className="flex flex-wrap items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-3">
            <IconTile icon="message-circle" />
            <Link href={`/help/${t.id}`} className="min-w-0 font-display text-[17px] font-semibold break-words text-accent underline-offset-2 hover:underline">
              {t.subject}
            </Link>
          </span>
          <Badge tone={statusTone(t.status)}>{STATUS_LABEL[t.status]}</Badge>
        </GlassCard>
      ))}
    </ul>
  );
}
