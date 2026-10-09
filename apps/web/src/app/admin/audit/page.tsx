import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { AuditPage } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Audit trail", robots: { index: false } };

const FILTERS = ["action", "actor_email", "target_type", "target_id", "before"] as const;
const when = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "medium" });

export default function AuditPageView({ searchParams }: PageProps<"/admin/audit">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Audit trail" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit trail</h1>
        <p className="text-muted">Every sensitive action, newest first. Records can&apos;t be edited or deleted; sensitive values are redacted. Your searches are recorded too.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Loading the audit trail" />}>
        {searchParams.then((sp) => (
          <Results params={Object.fromEntries(FILTERS.map((k) => [k, typeof sp[k] === "string" ? (sp[k] as string) : ""]))} />
        ))}
      </Suspense>
    </div>
  );
}

async function Results({ params }: { params: Record<string, string> }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/audit");
  if (!user.me.roles.includes("owner_admin")) return <Notice tone="warn" title="Owner and admins only">Only the owner or an administrator can open the audit trail.</Notice>;
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
  const res = await api<AuditPage>(`/v1/admin/audit?${qs.toString()}`, { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Multi-factor sign-in needed" : "Couldn't load the audit trail"}>
        {res.problem?.detail ?? "Please try again."}
      </Notice>
    );
  }
  const older = res.data.next_before ? `?${new URLSearchParams({ ...Object.fromEntries(qs), before: res.data.next_before }).toString()}` : null;
  return (
    <div className="space-y-4">
      <form method="get" className="grid gap-2 sm:grid-cols-4" aria-label="Filter the audit trail">
        <input name="action" defaultValue={params.action} placeholder="Action, e.g. content." aria-label="Action" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
        <input name="actor_email" defaultValue={params.actor_email} placeholder="Actor email" aria-label="Actor email" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
        <input name="target_type" defaultValue={params.target_type} placeholder="Target type" aria-label="Target type" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
        <div className="flex gap-2">
          <input name="target_id" defaultValue={params.target_id} placeholder="Target ID" aria-label="Target ID" className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
          <button type="submit" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:border-accent">
            Filter
          </button>
        </div>
      </form>
      {res.data.events.length === 0 ? (
        <Notice title="Nothing matches">Try a broader filter.</Notice>
      ) : (
        <ol className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Audit events">
          {res.data.events.map((e) => (
            <li key={e.id} className="space-y-1 p-3 text-sm">
              <p>
                <span className="font-medium">{e.action}</span> <span className="text-muted">· {when(e.at)} · {e.actor ?? "system"}</span>
              </p>
              <p className="text-muted">
                {e.target_type} {e.target_id}
              </p>
              {Object.keys(e.details).length > 0 && <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(e.details, null, 1)}</pre>}
            </li>
          ))}
        </ol>
      )}
      {older && (
        <Link href={`/admin/audit${older}`} className="inline-block text-accent underline underline-offset-2">
          Older events
        </Link>
      )}
    </div>
  );
}
