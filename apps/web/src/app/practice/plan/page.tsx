import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { StudyPlan } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Study plan", robots: { index: false } };

const field = "rounded-lg border border-border bg-surface px-3 py-2";
const hours = (m: number) => (m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`);
const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);

export default function PlanPage({ searchParams }: PageProps<"/practice/plan">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Study plan" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Study plan</h1>
        <p className="text-muted">
          A plan for one book up to your target date, weakest topics first. If there isn&apos;t enough time, it says so and shows what matters most. It doesn&apos;t predict exam
          results.
        </p>
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
    <form method="get" className="flex flex-wrap items-end gap-2" aria-label="Plan settings">
      <select name="grade" defaultValue={grade} aria-label="Class" className={field}>
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
      <label className="space-y-1 text-sm">
        <span className="block">Target date</span>
        <input type="date" name="target_date" defaultValue={target || inDays(60)} className={field} />
      </label>
      <label className="space-y-1 text-sm">
        <span className="block">Minutes a day</span>
        <input type="number" name="daily_minutes" min={10} max={600} defaultValue={daily || "60"} className={`${field} w-28`} />
      </label>
      <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent">
        Make my plan
      </button>
    </form>
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
    <div className="space-y-4">
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
      <ol className="divide-y divide-border rounded-xl border border-border bg-surface text-sm" aria-label="Plan">
        {p.schedule.map((x, i) => (
          <li key={i} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
            <span>
              {new Date(String(x.date)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} · Chapter {String(x.chapter_number)} · {String(x.label)}
            </span>
            <span className="text-muted">
              {String(x.minutes)} min · {String(x.why)}
            </span>
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted">
        Estimates: {String(p.assumptions.developing_minutes)} minutes for a developing topic, {String(p.assumptions.no_evidence_minutes)} for one without evidence; order:{" "}
        {String(p.assumptions.order)}. The plan updates from your latest answers, so a missed day simply replans.
      </p>
    </div>
  );
}
