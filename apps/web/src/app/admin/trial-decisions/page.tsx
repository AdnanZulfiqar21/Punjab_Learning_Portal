import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { TrialDecisionReport } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Trial decisions", robots: { index: false } };

const rate = (v: string | number | null) => (v === null ? "—" : `${String(v)}%`);

export default function TrialDecisionsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Trial decisions" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Trial decisions</h1>
        <p className="text-muted">
          How free-trial claims were decided each week: unknown device checks, refusals, appeals and refusals a reviewer later reversed. Test accounts are left out.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Preparing the report" />}>
        <Decisions />
      </Suspense>
    </div>
  );
}

async function Decisions() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/trial-decisions");
  const res = await api<TrialDecisionReport>("/v1/admin/analytics/trial-decisions", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load the report"}>
        {res.status === 403 ? "The owner, administrators and finance staff can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  const r = res.data;
  return (
    <div className="space-y-4">
      <Notice tone="warn" title="Not evidence about real devices">
        {r.evidence_note}
      </Notice>
      <Notice title="Who reviews appeals">{r.appeals_owner ?? r.appeals_owner_note}</Notice>
      {r.cohorts.length === 0 ? (
        <p className="text-muted">No trial claims from learners in the last {r.weeks} weeks.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full text-sm">
            <caption className="sr-only">Trial claims by week</caption>
            <thead className="text-left text-muted">
              <tr>
                {["Week", "Claims", "From the apps", "Unknown", "Refused", "Appealed", "Reversed", `Reversed (target under ${String(r.target_overturned_percent)}%)`, "In review", "Cost"].map((h) => (
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
                  <td className="px-3 py-2">{c.claims}</td>
                  <td className="px-3 py-2">{c.app_claims}</td>
                  <td className="px-3 py-2">
                    {c.unknown_verdicts} ({rate(c.unknown_rate)})
                  </td>
                  <td className="px-3 py-2">
                    {c.denials} ({rate(c.denial_rate)})
                  </td>
                  <td className="px-3 py-2">
                    {c.appeals} ({rate(c.appeal_rate)})
                  </td>
                  <td className="px-3 py-2">{c.overturned_denials}</td>
                  <td className="px-3 py-2">
                    {c.overturned_rate === null ? <span className="text-muted">no refusals</span> : rate(c.overturned_rate)}
                    {c.meets_target === false && <span className="font-medium text-danger"> above target</span>}
                  </td>
                  <td className="px-3 py-2">{c.review_required}</td>
                  <td className="px-3 py-2">
                    {c.trial_cost.length === 0 ? <span className="text-muted">rates not set</span> : c.trial_cost.map((x) => `${x.currency} ${String(x.amount)}`).join(" + ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-sm text-muted">Not measured yet: {r.unmeasured_costs.join("; ")}.</p>
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
