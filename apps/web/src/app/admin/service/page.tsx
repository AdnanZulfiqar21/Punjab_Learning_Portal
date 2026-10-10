import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { OpsSignal } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Service overview", robots: { index: false } };

const LEVEL: Record<string, { label: string; tone: "ok" | "warn" | "danger" | "info" }> = {
  ok: { label: "OK", tone: "ok" },
  warn: { label: "Warning", tone: "warn" },
  alert: { label: "Alert", tone: "danger" },
  unavailable: { label: "Not measured yet", tone: "info" },
};
const ORDER: Record<string, number> = { alert: 0, warn: 1, ok: 2, unavailable: 3 };
const fmt = (name: string, v: number) =>
  name.endsWith("_ratio") || name.includes("_ratio_") ? `${(v * 100).toFixed(2)}%` : name.endsWith("_s") ? `${Math.round(v)} s` : name.includes("_ms_") ? `${Math.round(v)} ms` : String(v);

export default function ServicePage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Service overview" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Service overview</h1>
        <p className="text-muted">
          Live signals with their thresholds, owners and runbooks. Request figures cover this server process over the last five minutes; queues and backlogs are read from the
          database. Signals that can&apos;t be measured yet say what they wait for.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Reading the signals" />}>
        <Signals />
      </Suspense>
    </div>
  );
}

async function Signals() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/service");
  const res = await api<OpsSignal[]>("/v1/ops/signals", { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Operators only" : "Couldn't read the signals"}>
        {res.status === 403 ? "Platform operators can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
      </Notice>
    );
  }
  const rows = [...res.data].sort((a, b) => (ORDER[a.level] ?? 9) - (ORDER[b.level] ?? 9) || a.name.localeCompare(b.name));
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr>
            {["Signal", "State", "Now", "Warn at", "Alert at", "Owner", "Runbook"].map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((s) => (
            <tr key={s.name}>
              <th scope="row" className="px-3 py-2 text-left font-mono text-xs font-normal">
                {s.name}
              </th>
              <td className="px-3 py-2">
                <Badge tone={LEVEL[s.level]?.tone ?? "info"}>{LEVEL[s.level]?.label ?? s.level}</Badge>
                {s.blocker && <span className="ml-2 text-xs text-muted">waits on {s.blocker}</span>}
              </td>
              <td className="px-3 py-2">{s.value === null ? "—" : fmt(s.name, s.value)}</td>
              <td className="px-3 py-2">{s.warn_at === null ? "—" : fmt(s.name, s.warn_at)}</td>
              <td className="px-3 py-2">{s.alert_at === null ? "—" : fmt(s.name, s.alert_at)}</td>
              <td className="px-3 py-2">{s.owner}</td>
              <td className="px-3 py-2 font-mono text-xs">{s.runbook}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
