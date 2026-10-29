import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { EvidenceReport } from "@portal/contracts";
import { Button } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { FIELD } from "@/components/practice-ui";
import { ProgressBar } from "@/components/progress-bar";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { api, currentUser } from "@/lib/session";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "What you've shown", robots: { index: false } };

const STATE: Record<string, { label: string; tone: "ok" | "warn" | "info" }> = {
  demonstrated: { label: "Demonstrated", tone: "ok" },
  developing: { label: "Developing", tone: "warn" },
  insufficient_evidence: { label: "Not enough evidence yet", tone: "info" },
};

export default function EvidencePage({ searchParams }: PageProps<"/practice/evidence">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "What you've shown" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Evidence"
          title="What you've shown"
          lead="Each topic is judged from your answers in the last 90 days. Repeating the same question doesn't count as new evidence. These are transparent rules, not a guarantee of exam results."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Working out your evidence" />}>
        {searchParams.then((sp) => (
          <Report grade={sp.grade === "12" ? 12 : 11} subject={typeof sp.subject === "string" && SUBJECTS.some(([k]) => k === sp.subject) ? sp.subject : "biology"} />
        ))}
      </Suspense>
    </div>
  );
}

async function Report({ grade, subject }: { grade: number; subject: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/evidence");
  const res = await api<EvidenceReport>(`/v1/me/evidence?grade=${grade}&subject=${subject}`, { token: user.token });
  return (
    <div className="space-y-6">
      <GlassCard padded={false} className="px-5 py-4">
        <form method="get" className="flex flex-wrap items-end gap-3" aria-label="Choose class and subject">
          <label className="space-y-1 text-sm">
            <span className="block font-medium">Class</span>
            <select name="grade" defaultValue={String(grade)} className={FIELD}>
              <option value="11">Class 11</option>
              <option value="12">Class 12</option>
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="block font-medium">Subject</span>
            <select name="subject" defaultValue={subject} className={FIELD}>
              {taughtSubjects(SUBJECTS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <Button type="submit">Show</Button>
        </form>
      </GlassCard>
      {!res.ok ? (
        <Notice tone="warn" title="Not available">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : (
        <>
          <dl className="grid gap-4 sm:grid-cols-3">
            {Object.entries(res.data.meters).map(([k, m]) => {
              const meter = m as { value: number | null; definition: string };
              const name = k.replace(/_/g, " ");
              return (
                <GlassCard key={k} className="space-y-2">
                  <dt className="text-sm font-medium text-muted capitalize">{name}</dt>
                  <dd className="font-display text-3xl font-bold tabular-nums">{meter.value === null ? "Unavailable" : `${meter.value}%`}</dd>
                  {meter.value !== null && (
                    <dd>
                      <ProgressBar value={meter.value} label={name} valueText={`${meter.value}%`} />
                    </dd>
                  )}
                  <dd className="text-xs text-muted">{meter.definition}</dd>
                </GlassCard>
              );
            })}
          </dl>
          <ul className="glass divide-y divide-border overflow-hidden rounded-card" aria-label="Topics">
            {res.data.outcomes.map((o) => (
              <li key={o.outcome_id} className="space-y-1 px-5 py-4 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  <Badge tone={STATE[o.state].tone}>{STATE[o.state].label}</Badge>
                  <span className="font-medium">
                    Chapter {o.chapter_number} · {o.label}
                  </span>
                </p>
                {o.reasons.length > 0 && <p className="text-muted">{o.reasons.join(" ")}</p>}
                {o.total_weight > 0 && (
                  <p className="text-xs text-muted">
                    Evidence weight {o.total_weight} from {o.families} question families
                    {o.weighted_accuracy !== null && ` · ${Math.round(o.weighted_accuracy * 100)}% weighted accuracy`} · first-time evidence {o.independent_weight}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">
            Rules: {res.data.rules_version}, evaluated {new Date(res.data.evaluated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE })}.
          </p>
        </>
      )}
    </div>
  );
}
