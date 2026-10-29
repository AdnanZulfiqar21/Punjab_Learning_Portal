import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { StudyPlan } from "@portal/contracts";
import { Button } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { FIELD } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { api, currentUser } from "@/lib/session";
import { daysFromToday } from "@/lib/dates";

export const metadata: Metadata = { title: "Study plan", robots: { index: false } };

const field = FIELD;
const hours = (m: number) => (m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`);
const inDays = daysFromToday; // the Pakistan day, not the UTC day (P12.S4.T3)

export default function PlanPage({ searchParams }: PageProps<"/practice/plan">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Study plan" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Planning"
          title="Study plan"
          lead="A plan for one book up to your target date, weakest topics first. If there isn't enough time, it says so and shows what matters most. It doesn't predict exam results."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Planning" />}>
        {searchParams.then((sp) => {
          const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
          return <Plan grade={one("grade") === "12" ? "12" : "11"} subject={SUBJECTS.some(([k]) => k === one("subject")) ? one("subject") : "biology"} target={one("target_date")} minutes={one("daily_minutes")} />;
        })}
      </Suspense>
    </div>
  );
}

async function Plan({ grade, subject, target, minutes }: { grade: string; subject: string; target: string; minutes: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/plan");
  const daily = minutes || String(user.me.profile?.daily_minutes ?? "");
  const form = (
    <GlassCard padded={false} className="px-5 py-4">
    <form method="get" className="flex flex-wrap items-end gap-3" aria-label="Plan settings">
      <label className="space-y-1 text-sm">
        <span className="block font-medium">Class</span>
        <select name="grade" defaultValue={grade} className={field}>
          <option value="11">Class 11</option>
          <option value="12">Class 12</option>
        </select>
      </label>
      <label className="space-y-1 text-sm">
        <span className="block font-medium">Subject</span>
        <select name="subject" defaultValue={subject} className={field}>
          {taughtSubjects(SUBJECTS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1 text-sm">
        <span className="block font-medium">Target date</span>
        <input type="date" name="target_date" defaultValue={target || inDays(60)} className={field} />
      </label>
      <label className="space-y-1 text-sm">
        <span className="block font-medium">Minutes a day</span>
        <input type="number" name="daily_minutes" min={10} max={600} defaultValue={daily || "60"} className={`${field} w-28`} />
      </label>
      <Button type="submit">Make my plan</Button>
    </form>
    </GlassCard>
  );
  if (!target) return form;
  const qs = new URLSearchParams({ grade, subject, target_date: target, ...(daily ? { daily_minutes: daily } : {}) });
  const res = await api<StudyPlan>(`/v1/me/study-plan?${qs.toString()}`, { token: user.token });
  if (!res.ok) {
    return (
      <div className="space-y-4">
        {form}
        <Notice tone="warn" title="Couldn't make a plan">
          {res.problem?.detail ?? "Please check the settings."}
        </Notice>
      </div>
    );
  }
  const p = res.data;
  return (
    <div className="space-y-6">
      {form}
      {p.feasible ? (
        <Notice title="This fits your time">
          About {hours(p.required_minutes)} of work over {p.days} days, with {hours(p.available_minutes)} available.
        </Notice>
      ) : (
        <Notice tone="warn" title={`About ${hours(p.shortfall_minutes)} short`}>
          This book needs about {hours(p.required_minutes)} but {p.days} days at {p.daily_minutes} minutes a day give {hours(p.available_minutes)}. The plan below covers the most
          important {p.schedule.length} topics; {p.unscheduled_topics} more won&apos;t fit unless you add time or move the date.
        </Notice>
      )}
      <section aria-labelledby="plan-h">
      <SectionHeader id="plan-h" title="Your plan" description={`${p.schedule.length} topic${p.schedule.length === 1 ? "" : "s"} over ${p.days} days.`} />
      <ol className="glass divide-y divide-border overflow-hidden rounded-card text-sm" aria-label="Plan">
        {p.schedule.map((x, i) => (
          <li key={i} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
            <span className="font-medium">
              {new Date(String(x.date)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })} · Chapter {String(x.chapter_number)} · {String(x.label)}
            </span>
            <span className="text-muted">
              {String(x.minutes)} min · {String(x.why)}
            </span>
          </li>
        ))}
      </ol>
      </section>
      <p className="text-xs text-muted">
        Estimates: {String(p.assumptions.developing_minutes)} minutes for a developing topic, {String(p.assumptions.no_evidence_minutes)} for one without evidence; order:{" "}
        {String(p.assumptions.order)}. The plan updates from your latest answers, so a missed day simply replans.
      </p>
    </div>
  );
}
