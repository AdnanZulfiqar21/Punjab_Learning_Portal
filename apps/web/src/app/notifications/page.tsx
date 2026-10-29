import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { Inbox, NotificationPreferences } from "@portal/contracts";
import { openNotification, readAllNotifications } from "@/app/actions/notifications";
import { buttonClasses } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { PageIcon } from "@/components/learner-pages";
import { PageHero } from "@/components/page-hero";
import { Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Notifications", robots: { index: false } };

export default function NotificationsPage() {
  return (
    <div className="space-y-6">
      <PageHero
        eyebrow="Account"
        title="Notifications"
        lead="Marks, requests from teachers and replies to your help requests."
        className="pt-2! pb-2! sm:pt-6!"
      />
      <div className="mx-auto max-w-2xl">
      <Suspense fallback={<SkeletonLines lines={5} label="Loading notifications" />}>
        <List />
      </Suspense>
      </div>
    </div>
  );
}

async function List() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/notifications");
  const [res, prefs] = await Promise.all([
    api<Inbox>("/v1/me/notifications?limit=50", { token: user.token }),
    api<NotificationPreferences>("/v1/me/notification-preferences", { token: user.token }),
  ]);
  // Times in the learner's chosen timezone (Asia/Karachi unless they changed it); stored in UTC.
  const timeZone = prefs.ok ? prefs.data.timezone : "Asia/Karachi";
  const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone });
  if (!res.ok) return <Notice tone="warn" title="Couldn't load notifications">Try again in a moment.</Notice>;
  const { items, unread } = res.data;
  if (items.length === 0) return <Notice title="Nothing yet">Marks, requests from teachers and replies to your help requests appear here.</Notice>;
  return (
    <GlassCard padded={false} className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-medium text-muted" role="status">
          <PageIcon name="bell" size={16} className="text-accent" />
          {unread} unread
        </p>
        {unread > 0 && (
          <form action={readAllNotifications}>
            <button type="submit" className={buttonClasses({ variant: "secondary" })}>
              <PageIcon name="check" size={16} />
              Mark all as read
            </button>
          </form>
        )}
      </div>
      <ul className="divide-y divide-border border-t border-border bg-surface" aria-label="Your notifications">
        {items.map((n) => (
          <li key={n.id}>
            <form action={openNotification.bind(null, n.id, n.link)}>
              <button type="submit" className="flex w-full items-start gap-3 px-5 py-4 text-left transition duration-200 hover:bg-surface-muted">
                <span aria-hidden="true" className={`mt-2 size-2 shrink-0 rounded-full ${n.read_at ? "bg-transparent" : "bg-accent"}`} />
                <span className="min-w-0 flex-1">
                  <span className={`block ${n.read_at ? "" : "font-semibold"}`}>
                    {n.read_at ? "" : <span className="sr-only">Unread: </span>}
                    {n.title}
                  </span>
                  <span className="block text-sm text-muted">{n.body}</span>
                  <span className="mt-0.5 block text-xs text-muted">{when(n.created_at)}</span>
                </span>
              </button>
            </form>
          </li>
        ))}
      </ul>
    </GlassCard>
  );
}
