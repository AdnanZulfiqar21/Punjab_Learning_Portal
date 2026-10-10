import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { FunnelReport } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Learning funnel", robots: { index: false } };

const pct = (n: number, of: number) => (of ? `${Math.round((100 * n) / of)}%` : "—");

export default function FunnelPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Learning funnel" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Learning funnel</h1>
        <p className="text-muted">
          Learners by the week they joined, and how many reached each step. Young cohorts are marked too early instead of counted as drop-off. Test accounts are left out.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Preparing the funnel" />}>
        <Funnel />
      </Suspense>
    </div>
  );
}

async function Funnel() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/funnel");
  const res = await api<FunnelReport>("/v1/admin/analytics/funnel", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load the funnel"}>
        {res.status === 403 ? "The owner, administrators and finance staff can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  const r = res.data;
  return (
    <div className="space-y-4">
      <Notice title="Data coverage">
        {r.events_since
          ? `Events have been recorded since ${new Date(r.events_since).toLocaleDateString("en-GB", { dateStyle: "medium" })}; activity before that isn't counted.`
          : "No events have been recorded yet."}
      </Notice>
      {r.cohorts.length === 0 ? (
        <p className="text-muted">No learners joined in the last 12 weeks.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                {["Week joined", "Age", "Joined", "First lesson", "First test", `Repeat study (${r.repeat_days} days)`, "Paid"].map((h) => (
                  <th key={h} scope="col" className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {r.cohorts.map((c) => (
                <tr key={c.week_start}>
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {c.week_start}
                  </th>
                  <td className="px-3 py-2">{c.age_days} days</td>
                  <td className="px-3 py-2">{c.signed_up}</td>
                  <td className="px-3 py-2">
                    {c.first_lesson} ({pct(c.first_lesson, c.signed_up)})
                  </td>
                  <td className="px-3 py-2">
                    {c.first_completed_test} ({pct(c.first_completed_test, c.signed_up)})
                  </td>
                  <td className="px-3 py-2">{c.repeat_study_too_early ? <span className="text-muted">too early</span> : `${c.repeat_study} (${pct(c.repeat_study, c.signed_up)})`}</td>
                  <td className="px-3 py-2 text-muted">unavailable ({c.paid_conversion.blocker})</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <dl className="space-y-1 text-sm">
        {Object.entries(r.definitions).map(([k, v]) => (
          <div key={k}>
            <dt className="inline font-medium">{k.replace(/_/g, " ")}: </dt>
            <dd className="inline text-muted">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
