import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { Inbox, NotificationPreferences } from "@portal/contracts";
import { openNotification, readAllNotifications } from "@/app/actions/notifications";
import { Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Notifications", robots: { index: false } };


export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Notifications</h1>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading notifications" />}>
        <List />
      </Suspense>
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
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted" role="status">
          {unread} unread
        </p>
        {unread > 0 && (
          <form action={readAllNotifications}>
            <button type="submit" className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium">
              Mark all as read
            </button>
          </form>
        )}
      </div>
      <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Your notifications">
        {items.map((n) => (
          <li key={n.id} className="px-4 py-3">
            <form action={openNotification.bind(null, n.id, n.link)}>
              <button type="submit" className="w-full text-left">
                <span className={`block ${n.read_at ? "" : "font-semibold"}`}>
                  {n.read_at ? "" : "● "}
                  {n.title}
                </span>
                <span className="block text-sm text-muted">{n.body}</span>
                <span className="block text-xs text-muted">{when(n.created_at)}</span>
              </button>
            </form>
          </li>
        ))}
      </ul>
    </div>
  );
}
