import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { EconomicsReport } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { TIME_ZONE } from "@/lib/dates";
import { api, currentUser } from "@/lib/session";
import { RateForm } from "./rate-form";

export const metadata: Metadata = { title: "Cohort economics", robots: { index: false } };

const TITLES: Record<string, string> = {
  paying: "Paying learners",
  trial: "Learners on a trial",
  completed_trial: "Trials that ended without paying",
};
const money = (m: { currency: string; amount: string | number }[]) => (m.length ? m.map((x) => `${x.currency} ${String(x.amount)}`).join(" + ") : "—");
const qty = (v: string | number | null) => (v === null ? "not measured" : String(Number(v).toLocaleString("en-GB", { maximumFractionDigits: 4 })));

export default function EconomicsPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Cohort economics" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Cohort economics</h1>
        <p className="text-muted">
          What each group of learners costs: measured usage times the rates finance entered. Anything not yet measured or priced is listed, never estimated.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={10} label="Preparing the report" />}>
        <Economics />
      </Suspense>
    </div>
  );
}

async function Economics() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/economics");
  const res = await api<EconomicsReport>("/v1/admin/analytics/economics", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load the report"}>
        {res.status === 403 ? "The owner, administrators and finance staff can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  const r = res.data;
  const finance = user.me.roles.includes("finance");
  return (
    <div className="space-y-8">
      <Notice title="For the owner's decision (D13)">
        The owner reviews this report, then sets the cohort budget, fair-use terms and rollout limits before paying for learner acquisition. Totals here are the known part only, for the last {r.window_days} days.
      </Notice>
      {r.populations.map((p) => (
        <section key={p.key} aria-labelledby={`pop-${p.key}`} className="space-y-3">
          <h2 id={`pop-${p.key}`} className="text-lg font-semibold">
            {TITLES[p.key] ?? p.key} <span className="font-normal text-muted">· {p.learners} learners</span>
          </h2>
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-sm">
              <caption className="sr-only">Costs for {TITLES[p.key] ?? p.key}</caption>
              <thead className="text-left text-muted">
                <tr>
                  {["Cost line", "Quantity", "Cost"].map((h) => (
                    <th key={h} scope="col" className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {p.lines.map((l) => (
                  <tr key={l.key}>
                    <th scope="row" className="px-3 py-2 text-left font-normal">
                      {l.label}
                      <span className="block text-xs text-muted">{l.quantity_note}</span>
                    </th>
                    <td className="px-3 py-2">
                      {qty(l.quantity)}
                      {l.blocker && <span className="text-muted"> ({l.blocker})</span>}
                    </td>
                    <td className="px-3 py-2">{l.cost !== null ? `${l.currency} ${String(l.cost)}` : <span className="text-muted">{l.quantity === null ? "unknown" : "rate not set"}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm">
            Known cost: <strong>{money(p.known_cost)}</strong> · per learner: <strong>{money(p.known_cost_per_learner)}</strong>
          </p>
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Not included yet ({p.missing.length})</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
              {p.missing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </details>
        </section>
      ))}
      <p className="text-sm">
        Contribution per paying learner: <span className="text-muted">unavailable until payments exist ({r.contribution_per_paying_learner.blocker})</span>
      </p>
      <section aria-labelledby="rates-h" className="space-y-3">
        <h2 id="rates-h" className="text-lg font-semibold">
          Rates
        </h2>
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm" aria-label="Current rates">
          {r.rates.map((x) => (
            <li key={x.key} className="px-3 py-2">
              <span className="font-medium">{x.label}</span> <span className="text-muted">({x.unit})</span>:{" "}
              {x.amount !== null ? (
                <>
                  {x.currency} {String(x.amount)}
                  <span className="block text-xs text-muted">
                    {x.source_note}
                    {x.set_at && ` · set ${new Date(x.set_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE })}`}
                  </span>
                </>
              ) : (
                <span className="text-muted">not set</span>
              )}
            </li>
          ))}
        </ul>
        {finance ? <RateForm rates={r.rates} /> : <p className="text-sm text-muted">Finance staff enter rates.</p>}
      </section>
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
