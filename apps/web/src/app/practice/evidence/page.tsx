import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { EvidenceReport } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "What you've shown", robots: { index: false } };

const STATE: Record<string, { label: string; tone: "ok" | "warn" | "info" }> = {
  demonstrated: { label: "Demonstrated", tone: "ok" },
  developing: { label: "Developing", tone: "warn" },
  insufficient_evidence: { label: "Not enough evidence yet", tone: "info" },
};

export default function EvidencePage({ searchParams }: PageProps<"/practice/evidence">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "What you've shown" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">What you&apos;ve shown</h1>
        <p className="text-muted">
          Each topic is judged from your answers in the last 90 days. Repeating the same question doesn&apos;t count as new evidence. These are transparent rules, not a guarantee of exam
          results.
        </p>
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
    <div className="space-y-4">
      <form method="get" className="flex flex-wrap items-end gap-2" aria-label="Choose class and subject">
        <select name="grade" defaultValue={String(grade)} aria-label="Class" className="rounded-lg border border-border bg-surface px-3 py-2">
          <option value="11">Class XI</option>
          <option value="12">Class XII</option>
        </select>
        <select name="subject" defaultValue={subject} aria-label="Subject" className="rounded-lg border border-border bg-surface px-3 py-2">
          {SUBJECTS.map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent">
          Show
        </button>
      </form>
      {!res.ok ? (
        <Notice tone="warn" title="Not available">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : (
        <>
          <dl className="grid gap-3 sm:grid-cols-3">
            {Object.entries(res.data.meters).map(([k, m]) => {
              const meter = m as { value: number | null; definition: string };
              return (
                <div key={k} className="rounded-xl border border-border bg-surface p-3">
                  <dt className="text-sm text-muted">{k.replace(/_/g, " ")}</dt>
                  <dd className="text-xl font-semibold">{meter.value === null ? "Unavailable" : `${meter.value}%`}</dd>
                  <dd className="text-xs text-muted">{meter.definition}</dd>
                </div>
              );
            })}
          </dl>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Topics">
            {res.data.outcomes.map((o) => (
              <li key={o.outcome_id} className="space-y-1 p-3 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  <Badge tone={STATE[o.state].tone}>{STATE[o.state].label}</Badge>
                  <span>
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
            Rules: {res.data.rules_version}, evaluated {new Date(res.data.evaluated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}.
          </p>
        </>
      )}
    </div>
  );
}
