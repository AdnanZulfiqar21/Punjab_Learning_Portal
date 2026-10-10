import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { BusinessOverview } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Business overview", robots: { index: false } };

const SOURCE: Record<string, string> = { trial: "Free trial", paid: "Paid", scholarship: "Scholarship", promotional: "Promotional", pilot: "Pilot" };

export default function BusinessPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Business overview" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Business overview</h1>
        <p className="text-muted">Aggregate figures only. Test accounts are counted separately and left out of everything else. Figures the portal can&apos;t know yet say so.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Preparing the overview" />}>
        <Overview />
      </Suspense>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-xl font-semibold">{value}</dd>
      {note && <dd className="text-xs text-muted">{note}</dd>}
    </div>
  );
}

async function Overview() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/business");
  const res = await api<BusinessOverview>("/v1/admin/business-overview", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load the overview"}>
        {res.status === 403 ? "The owner, administrators and finance staff can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  const r = res.data;
  const pending = (u: { available: boolean; blocker: string }) => (u.available ? undefined : `Unavailable until payments are connected (${u.blocker}).`);
  return (
    <div className="space-y-6">
      <dl className="grid gap-3 sm:grid-cols-4">
        <Stat label="Learners" value={String(r.learners)} />
        <Stat label="Active in 7 days" value={String(r.active_7d)} />
        <Stat label="Active in 30 days" value={String(r.active_30d)} />
        <Stat label="Test accounts (excluded)" value={String(r.test_accounts)} />
      </dl>
      <section aria-labelledby="access-h" className="space-y-2">
        <h2 id="access-h" className="font-semibold">
          Access now
        </h2>
        <dl className="grid gap-3 sm:grid-cols-5">
          {Object.entries(r.entitlements_active).map(([k, v]) => (
            <Stat key={k} label={SOURCE[k] ?? k} value={String(v)} />
          ))}
        </dl>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Stat label="Verified purchases" value={r.verified_purchases.available ? String(r.verified_purchases.value) : "—"} note={pending(r.verified_purchases)} />
          <Stat label="Refunds" value={r.refunds.available ? String(r.refunds.value) : "—"} note={pending(r.refunds)} />
          <Stat label="Revenue" value="—" note={pending(r.revenue)} />
        </dl>
      </section>
      <section aria-labelledby="cohorts-h" className="space-y-2">
        <h2 id="cohorts-h" className="font-semibold">
          Trial cohorts (last 12 weeks)
        </h2>
        {r.trial_cohorts.length === 0 ? (
          <p className="text-muted">No trials started in the last 12 weeks.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  {["Week starting", "Started", "Still running", "Ended", "Converted to paid"].map((h) => (
                    <th key={h} scope="col" className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {r.trial_cohorts.map((c) => (
                  <tr key={c.week_start}>
                    <th scope="row" className="px-3 py-2 text-left font-normal">
                      {c.week_start}
                      {c.open && <span className="ml-2 text-xs text-muted">open cohort</span>}
                    </th>
                    <td className="px-3 py-2">{c.started}</td>
                    <td className="px-3 py-2">{c.running}</td>
                    <td className="px-3 py-2">{c.ended}</td>
                    <td className="px-3 py-2">{c.converted_to_paid}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section aria-labelledby="usage-h" className="space-y-2">
        <h2 id="usage-h" className="font-semibold">
          Content usage (30 days)
        </h2>
        <dl className="grid gap-3 sm:grid-cols-4">
          <Stat label="Lessons completed" value={String(r.content_usage_30d.lessons_completed)} />
          <Stat label="Tests submitted" value={String(r.content_usage_30d.tests_submitted)} />
          <Stat label="Written tests sealed" value={String(r.content_usage_30d.written_sealed)} />
          <Stat label="Learners doing any of these" value={String(r.content_usage_30d.engaged_learners)} />
        </dl>
      </section>
      <section aria-labelledby="defs-h" className="space-y-1 text-sm">
        <h2 id="defs-h" className="font-semibold">
          What these figures mean
        </h2>
        <dl className="space-y-1">
          {Object.entries(r.definitions).map(([k, v]) => (
            <div key={k}>
              <dt className="inline font-medium">{k.replace(/_/g, " ")}: </dt>
              <dd className="inline text-muted">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
