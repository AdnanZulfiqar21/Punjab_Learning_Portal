import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { ExportJob } from "@portal/contracts";
import { cancelExport, retryExport } from "@/app/actions/exports";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { ExportRequestForm } from "./request-form";

export const metadata: Metadata = { title: "Exports", robots: { index: false } };

const KIND: Record<string, string> = { personal_data: "Your personal data (JSON)", audit_events: "Audit trail (CSV, redacted)" };
const STATUS: Record<string, { label: string; tone: "info" | "warn" | "ok" | "danger" }> = {
  queued: { label: "Waiting", tone: "info" },
  running: { label: "Preparing", tone: "info" },
  ready: { label: "Ready", tone: "ok" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "warn" },
  expired: { label: "Expired", tone: "warn" },
};
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

export default function ExportsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Exports" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Exports</h1>
        <p className="text-muted">
          Exports are prepared in the background. Only you can see or download yours, and each download is recorded. A file is kept for 24 hours.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading your exports" />}>
        <Exports />
      </Suspense>
    </div>
  );
}

async function Exports() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/account/exports");
  const res = await api<ExportJob[]>("/v1/exports", { token: user.token });
  const canAudit = user.me.roles.includes("owner_admin");
  return (
    <div className="space-y-6">
      <ExportRequestForm canAudit={canAudit} />
      {!res.ok ? (
        <Notice tone="warn" title="Couldn't load your exports">
          Please try again.
        </Notice>
      ) : res.data.length === 0 ? (
        <p className="text-muted">You haven&apos;t requested any exports yet.</p>
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Your exports">
          {res.data.map((j) => (
            <li key={j.id} className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm">
              <div className="space-y-1">
                <p className="flex flex-wrap items-center gap-2">
                  <Badge tone={STATUS[j.status].tone}>{STATUS[j.status].label}</Badge>
                  <span className="font-medium">{KIND[j.kind] ?? j.kind}</span>
                </p>
                <p className="text-muted">
                  Requested {when(j.created_at)}
                  {j.row_count !== null && ` · ${j.row_count} rows`}
                  {j.expires_at && j.status === "ready" && ` · available until ${when(j.expires_at)}`}
                  {j.downloads > 0 && ` · downloaded ${j.downloads}×`}
                </p>
                {j.error && <p className="text-muted">{j.error}</p>}
              </div>
              <div className="flex gap-2">
                {j.status === "ready" && (
                  <a href={`/account/exports/${j.id}/download`} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
                    Download
                  </a>
                )}
                {(j.status === "queued" || j.status === "running") && (
                  <form action={cancelExport.bind(null, j.id)}>
                    <button type="submit" className="rounded-lg border border-border bg-surface px-3 py-1.5 hover:border-accent">
                      Cancel
                    </button>
                  </form>
                )}
                {j.status === "failed" && (
                  <form action={retryExport.bind(null, j.id)}>
                    <button type="submit" className="rounded-lg border border-border bg-surface px-3 py-1.5 hover:border-accent">
                      Try again
                    </button>
                  </form>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
