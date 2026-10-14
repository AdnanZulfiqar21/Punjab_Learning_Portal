import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { BacklogRow, ClientPlatformState, Integration, OpsSignal, RolloutSnapshot } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";
import { ClientMinimumForm } from "./client-minimum-form";
import { RolloutForm } from "./rollout-form";
import { StaffingForm } from "./staffing-form";
import { TIME_ZONE } from "@/lib/dates";

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
      <Suspense fallback={<SkeletonLines lines={6} label="Checking integrations" />}>
        <Integrations />
      </Suspense>
      <Suspense fallback={<SkeletonLines lines={4} label="Reading feature rollouts" />}>
        <Rollouts />
      </Suspense>
      <Suspense fallback={<SkeletonLines lines={4} label="Reading supported app versions" />}>
        <ClientVersions />
      </Suspense>
      <Suspense fallback={<SkeletonLines lines={4} label="Reading written-review staffing" />}>
        <ReviewStaffing />
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

const MODE: Record<string, { label: string; tone: "ok" | "warn" | "danger" | "info" }> = {
  live: { label: "Live", tone: "ok" },
  development: { label: "Development stand-in", tone: "info" },
  unavailable: { label: "Not connected", tone: "warn" },
};

async function Integrations() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/service");
  const res = await api<Integration[]>("/v1/ops/integrations", { token: user.token });
  if (!res.ok) return null; // the signals panel above already explains access problems
  return (
    <section aria-labelledby="integrations-h" className="space-y-2">
      <h2 id="integrations-h" className="font-semibold">
        Integrations
      </h2>
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              {["Provider", "Mode", "Adapter", "Health", "Last 24 hours", "Daily budget"].map((h) => (
                <th key={h} scope="col" className="px-3 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {res.data.map((i) => (
              <tr key={i.key}>
                <th scope="row" className="px-3 py-2 text-left font-normal">
                  {i.name}
                </th>
                <td className="px-3 py-2">
                  <Badge tone={MODE[i.mode]?.tone ?? "info"}>{MODE[i.mode]?.label ?? i.mode}</Badge>
                  {i.blocker && <span className="ml-2 text-xs text-muted">waits on {i.blocker}</span>}
                </td>
                <td className="px-3 py-2 font-mono text-xs">{i.adapter}</td>
                <td className="px-3 py-2">{i.health === "not_checked" ? "—" : i.health}</td>
                <td className="px-3 py-2">
                  {Object.keys(i.usage_24h).length === 0 ? "—" : Object.entries(i.usage_24h).map(([k, v]) => `${k} ${v}`).join(", ")}
                </td>
                <td className="px-3 py-2">
                  {i.budget_daily === null ? "not set" : `${i.budget_daily}${i.budget_used_ratio === null ? "" : ` (${Math.round(i.budget_used_ratio * 100)}% used)`}`}
                  {i.level !== "ok" && <Badge tone={i.level === "alert" ? "danger" : "warn"}>{i.level}</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// P16.S3.T1 (ROLLOUT-01): the share of learners who get each feature in this environment. A flag only ever hides a
// feature; staff always see it so it can be checked first. Changes need a reason and are audited.
async function Rollouts() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/service");
  const res = await api<RolloutSnapshot>("/v1/ops/rollouts", { token: user.token });
  if (!res.ok) return null; // the signals panel above already explains access problems
  return (
    <section aria-labelledby="rollouts-h" className="space-y-2">
      <h2 id="rollouts-h" className="font-semibold">
        Feature rollouts <span className="font-normal text-muted">({res.data.environment})</span>
      </h2>
      <p className="text-sm text-muted">
        Learners are placed in or out by a stable hash of the feature and their account, so their answer doesn&apos;t change between visits. Staff always see the feature.
        Lowering a rollout hides the feature; it never deletes anything learners kept.
      </p>
      <ul className="space-y-3">
        {res.data.rollouts.map((r) => (
          <li key={r.key} className="space-y-3 rounded-xl border border-border bg-surface p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <p className="font-medium">{r.description}</p>
                <p className="font-mono text-xs text-muted">{r.key}</p>
              </div>
              <p className="text-sm">
                <Badge tone={r.percent === 100 ? "ok" : r.percent === 0 ? "warn" : "info"}>{r.percent}% of learners</Badge>
                <span className="ml-2 text-muted">default {r.default_percent}%</span>
              </p>
            </div>
            {r.reason && (
              <p className="text-sm text-muted">
                Last change{r.updated_at ? ` on ${new Date(r.updated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE })}` : ""}: {r.reason}
              </p>
            )}
            <RolloutForm rolloutKey={r.key} label={r.description} percent={r.percent} />
          </li>
        ))}
      </ul>
    </section>
  );
}

const PLATFORM_NAME: Record<string, string> = { android: "Android", ios: "iPhone and iPad" };
const at = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });

// P13.S1.T4 (CLIENTS-01): the oldest app version each platform still serves, and the builds' capability manifests.
async function ClientVersions() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/service");
  const res = await api<ClientPlatformState[]>("/v1/ops/clients", { token: user.token });
  if (!res.ok) return null; // the signals panel above already explains access problems
  return (
    <section aria-labelledby="clients-h" className="space-y-2">
      <h2 id="clients-h" className="font-semibold">
        Supported app versions
      </h2>
      <p className="text-sm text-muted">
        Raising a minimum gives learners at least 14 days&apos; notice and never takes effect inside a scheduled mock window. After it, an older app is told to
        update instead of working. Lowering it applies at once. The web app is always current.
      </p>
      <ul className="space-y-3">
        {res.data.map((p) => {
          const name = PLATFORM_NAME[p.platform] ?? p.platform;
          return (
            <li key={p.platform} className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-medium">{name}</p>
                <p>
                  {p.min_version ? (
                    <>
                      Minimum <span className="font-mono">{p.min_version}</span>
                      {p.enforce_at ? <span className="text-muted"> · in effect from {at(p.enforce_at)}</span> : null}
                    </>
                  ) : (
                    <span className="text-muted">No minimum set: every version is served.</span>
                  )}
                </p>
              </div>
              {p.reason && <p className="text-muted">Reason: {p.reason}</p>}
              <p className="text-muted">
                {p.manifests.length === 0
                  ? "No build has registered its capability manifest yet."
                  : `Registered builds: ${p.manifests.map((m) => `${m.app_version} (renderer ${m.renderer_version}, packs v${m.pack_format_version})`).join(", ")}.`}
              </p>
              <ClientMinimumForm platform={p.platform} label={name} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const SUBJECT_NAME: Record<string, string> = {
  biology: "Biology",
  chemistry: "Chemistry",
  physics: "Physics",
  computer_science: "Computer Science",
  mathematics: "Mathematics",
};

// W06.S3.T2 (STAFFING-01): written-review capacity per class and subject, with the staffing behind it. New tests are
// admitted only while the hours left after fixed obligations and owed work cover another script within the turnaround.
async function ReviewStaffing() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/service");
  const res = await api<BacklogRow[]>("/v1/ops/written-backlog", { token: user.token });
  if (!res.ok) return null; // the signals panel above already explains access problems
  return (
    <section aria-labelledby="staffing-h" className="space-y-2">
      <h2 id="staffing-h" className="font-semibold">
        Written-review staffing
      </h2>
      <p className="text-sm text-muted">
        Fixed obligations come off the productive hours first, then the work already owed (queued scripts and started tests). New written tests start only
        while what is left covers another script within the promised turnaround. Scripts already accepted are always marked, and no answer is ever approved
        automatically to clear a backlog.
      </p>
      {res.data.length === 0 ? (
        <p className="text-sm text-muted">No class and subject has review capacity yet.</p>
      ) : (
        <ul className="space-y-3">
          {res.data.map((r) => {
            const label = `Class ${r.grade === 11 ? "XI" : "XII"} ${SUBJECT_NAME[r.subject] ?? r.subject}`;
            const s = r.staffing;
            return (
              <li key={`${r.grade}-${r.subject}`} className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium">{label}</p>
                  <Badge tone={r.accepting ? "ok" : "warn"}>{r.accepting ? "Accepting new tests" : "Not accepting new tests"}</Badge>
                </div>
                <p className="text-muted">
                  {r.open_cases} queued · {r.open_permits} started, not yet submitted · {r.overdue_cases} overdue · case limit {r.max_open_cases}
                </p>
                {/* QUEUE-AGEING-01: waiting time against the proposed 24 h / 48 h targets */}
                {r.open_cases > 0 && (
                  <p className={(r.queued_over_48h ?? 0) > 0 ? "text-danger" : "text-muted"}>
                    Waiting: {r.queued_under_24h ?? 0} under 24 hours · {r.queued_24_to_48h ?? 0} for 24 to 48 hours · {r.queued_over_48h ?? 0} for more than 48
                    hours
                    {r.oldest_queued_at ? ` · the longest since ${new Date(r.oldest_queued_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE })}` : ""}
                  </p>
                )}
                <p className="text-muted">
                  {s
                    ? `${s.available_minutes} minutes available within ${s.turnaround_days} days, ${s.due_minutes} already owed: room for ${s.admissible_scripts} more script${s.admissible_scripts === 1 ? "" : "s"}.` +
                      (s.turnaround_estimate_days !== null
                        ? ` A test started now would wait about ${s.turnaround_estimate_days} day${s.turnaround_estimate_days === 1 ? "" : "s"}.`
                        : " Nobody is available to mark.")
                    : "No staffing recorded: only the case limit applies."}
                </p>
                <StaffingForm row={r} label={label} />
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
