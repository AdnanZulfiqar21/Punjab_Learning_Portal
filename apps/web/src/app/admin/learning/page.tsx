import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { LearningReport } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Learning and engagement", robots: { index: false } };

const field = "rounded-lg border border-border bg-surface px-3 py-2";

export default function LearningPage({ searchParams }: PageProps<"/admin/learning">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/account", label: "Account" }, { label: "Learning and engagement" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Learning and engagement</h1>
        <p className="text-muted">What learners have shown they know, beside how much they use the material, for one book. The two are never blended into one score.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Preparing the report" />}>
        {searchParams.then((sp) => (
          <Report grade={sp.grade === "12" ? 12 : 11} subject={typeof sp.subject === "string" && SUBJECTS.some(([k]) => k === sp.subject) ? sp.subject : "biology"} />
        ))}
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

async function Report({ grade, subject }: { grade: number; subject: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/admin/learning");
  const res = await api<LearningReport>(`/v1/admin/analytics/learning?grade=${grade}&subject=${subject}`, { token: user.token });
  const form = (
    <form method="get" className="flex flex-wrap items-end gap-2" aria-label="Choose a book">
      <select name="grade" defaultValue={String(grade)} aria-label="Class" className={field}>
        <option value="11">Class XI</option>
        <option value="12">Class XII</option>
      </select>
      <select name="subject" defaultValue={subject} aria-label="Subject" className={field}>
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
  );
  if (!res.ok) {
    return (
      <div className="space-y-4">
        {form}
        <Notice tone="warn" title={res.status === 403 ? "Not available to you" : "Couldn't load the report"}>
          {res.status === 403 ? "The owner, administrators and finance staff can open this, with a multi-factor sign-in." : (res.problem?.detail ?? "Please try again.")}
        </Notice>
      </div>
    );
  }
  const r = res.data;
  const o = r.outcomes;
  const e = r.engagement;
  return (
    <div className="space-y-6">
      {form}
      <section aria-labelledby="outcomes-h" className="space-y-2">
        <h2 id="outcomes-h" className="font-semibold">
          Outcomes: what learners have shown
        </h2>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Stat label="Learners assessed" value={String(o.learners_assessed)} note={`Most recently active, at most ${o.sample_limit}; learners without answers in 90 days aren't assessed.`} />
          <Stat label="Median topics demonstrated" value={o.median_demonstrated_pct === null ? "—" : `${o.median_demonstrated_pct}%`} note={`Of ${o.topics_in_book} topics, ${o.rules_version}.`} />
          <Stat label="Syllabus coverage" value="—" note={`Unavailable until exam outcomes are mapped (${r.unavailable.syllabus_coverage}).`} />
        </dl>
        <ul className="flex flex-wrap gap-2 text-sm" aria-label="Distribution of topics demonstrated">
          {o.distribution.map((b) => (
            <li key={`${b.from}-${b.to}`} className="rounded-lg border border-border bg-surface px-3 py-1">
              {b.from === 0 && b.to === 0 ? "0%" : `${b.from}–${b.to}%`}: {b.learners}
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="engagement-h" className="space-y-2">
        <h2 id="engagement-h" className="font-semibold">
          Engagement: how the material is used
        </h2>
        <dl className="grid gap-3 sm:grid-cols-4">
          <Stat label="Live lessons" value={String(e.live_lessons)} />
          <Stat label="Learners completing lessons" value={String(e.learners_completing)} />
          <Stat label="Median lessons completed" value={e.median_completed_pct === null ? "—" : `${e.median_completed_pct}%`} />
          <Stat label="Lesson visit days (30 days)" value={String(e.lesson_visit_days_30d)} note={`Watch time unavailable (${r.unavailable.watch_time}).`} />
        </dl>
      </section>
      <Notice title="Reading these together">{r.note}</Notice>
    </div>
  );
}
