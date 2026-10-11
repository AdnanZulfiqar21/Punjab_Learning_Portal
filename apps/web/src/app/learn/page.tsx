import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { Discovery } from "@portal/contracts";
import { getDiscovery } from "@/lib/api";
import { GRADE_LABEL } from "@/lib/format";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";

export const metadata: Metadata = { title: "Learn" };

const SUBJECTS: [string, string][] = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
];
const AVAILABILITY: [string, string][] = [
  ["all", "Everything"],
  ["lessons", "Has reviewed lessons"],
  ["previews", "Has free previews"],
  ["practice", "Has practice questions"],
];
type Filters = { grade?: string; track?: string; subject?: string; exam?: string; availability?: string };
const TRACK_CODES = ["pre_medical", "pre_engineering", "ics"];
/** Only known values reach the API; anything hand-edited into the URL is ignored rather than shown as an error. */
const pick = (v: string | string[] | undefined, allowed?: string[]) =>
  typeof v === "string" && v && (!allowed || allowed.includes(v)) ? v : undefined;

/** P11.S1.T3 (DISCOVERY-01): what is actually published per book, with filters. Class XI and XII stay separate. */
export default function LearnPage({ searchParams }: PageProps<"/learn">) {
  return (
    <div className="space-y-6">
      <div>
        <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Learn" }]} />
        <h1 className="mb-2 text-2xl font-semibold tracking-tight">Choose your class and subject</h1>
        <p className="text-muted">
          Class XI and Class XII use different textbooks and are listed separately. Each book shows what has been
          reviewed and published so far.
        </p>
      </div>
      <Suspense fallback={<SkeletonCards count={10} label="Loading subjects" />}>
        {searchParams.then((sp) => (
          <Discover
            filters={{
              grade: pick(sp.grade, ["11", "12"]),
              track: pick(sp.track, TRACK_CODES),
              subject: pick(sp.subject, SUBJECTS.map(([c]) => c)),
              exam: typeof sp.exam === "string" && /^[A-Za-z0-9_-]{2,40}$/.test(sp.exam) ? sp.exam : undefined,
              availability: pick(sp.availability, AVAILABILITY.map(([v]) => v)),
            }}
          />
        ))}
      </Suspense>
    </div>
  );
}

function summary(b: Discovery["books"][number]): string {
  if (b.state === "not_yet_published") return "No reviewed lessons or practice questions published yet.";
  const parts = [];
  if (b.live_lessons) parts.push(`${b.live_lessons} reviewed lesson${b.live_lessons === 1 ? "" : "s"} in ${b.chapters_with_lessons} ${b.chapter_label.toLowerCase()}${b.chapters_with_lessons === 1 ? "" : "s"}`);
  else parts.push("No reviewed lessons yet");
  if (b.preview_lessons) parts.push(`${b.preview_lessons} free preview${b.preview_lessons === 1 ? "" : "s"}`);
  if (b.practice_questions) parts.push(`${b.practice_questions} practice question${b.practice_questions === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

async function Discover({ filters }: { filters: Filters }) {
  const res = await getDiscovery(filters);
  if (!res.ok) {
    return (
      <Notice tone="warn" title="Nothing matches that filter">
        {res.problem.detail} <Link href="/learn" className="underline">Show everything</Link>
      </Notice>
    );
  }
  const d = res.data;
  const select = "rounded-lg border border-border bg-surface px-3 py-2";
  const grades = [11, 12].filter((g) => d.books.some((b) => b.grade === g));
  return (
    <div className="space-y-8">
      <form method="get" action="/learn" aria-label="Filter subjects" className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-surface p-4 text-sm">
        <div className="flex flex-col gap-1">
          <label htmlFor="f-grade">Class</label>
          <select id="f-grade" name="grade" defaultValue={filters.grade ?? ""} className={select}>
            <option value="">Both classes</option>
            <option value="11">Class XI</option>
            <option value="12">Class XII</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="f-track">Track</label>
          <select id="f-track" name="track" defaultValue={filters.track ?? ""} className={select}>
            <option value="">Any track</option>
            {d.tracks.map((t) => (
              <option key={t.code} value={t.code}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="f-subject">Subject</label>
          <select id="f-subject" name="subject" defaultValue={filters.subject ?? ""} className={select}>
            <option value="">Any subject</option>
            {SUBJECTS.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>
        {d.exams.length > 0 && (
          <div className="flex flex-col gap-1">
            <label htmlFor="f-exam">Exam</label>
            <select id="f-exam" name="exam" defaultValue={filters.exam ?? ""} className={select}>
              <option value="">Any exam</option>
              {d.exams.map((e) => (
                <option key={e.code} value={e.code}>
                  {e.name} {e.year}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex flex-col gap-1">
          <label htmlFor="f-availability">Show</label>
          <select id="f-availability" name="availability" defaultValue={filters.availability ?? "all"} className={select}>
            {AVAILABILITY.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong dark:text-background">
          Apply
        </button>
        {Object.values(filters).some(Boolean) && (
          <Link href="/learn" className="py-2 text-accent underline underline-offset-2">
            Clear filters
          </Link>
        )}
      </form>
      {d.exams.length === 0 && (
        <p className="text-sm text-muted">MDCAT and ECAT exam filters appear once their official patterns have been verified.</p>
      )}
      {filters.track && <p className="text-sm text-muted">{d.tracks.find((t) => t.code === filters.track)?.note}</p>}

      {d.books.length === 0 ? (
        <Notice title="Nothing matches these filters yet">
          Try another class or subject, or <Link href="/learn" className="underline">show everything</Link>.
        </Notice>
      ) : (
        <div className="grid gap-8 md:grid-cols-2">
          {grades.map((g) => (
            <section key={g} aria-labelledby={`grade-${g}`}>
              <h2 id={`grade-${g}`} className="mb-3 text-lg font-semibold">
                {GRADE_LABEL[g]}
              </h2>
              <ul className="space-y-2">
                {d.books
                  .filter((b) => b.grade === g)
                  .map((b) => (
                    <li key={b.book_id}>
                      <Link
                        href={`/learn/${b.grade}/${b.subject}`}
                        className="flex items-start justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3 hover:border-accent"
                      >
                        <span>
                          <span className="block font-medium">{b.subject_name}</span>
                          <span className="block text-sm text-muted">
                            {b.chapter_count} {b.chapter_label.toLowerCase()}s · {summary(b)}
                          </span>
                        </span>
                        <span className="flex shrink-0 flex-col items-end gap-1">
                          {b.state === "not_yet_published" && <Badge>Outline only</Badge>}
                          {b.preview_lessons > 0 && <Badge tone="ok">Free previews</Badge>}
                          {b.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
                        </span>
                      </Link>
                    </li>
                  ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {d.previews.length > 0 && (
        <section aria-labelledby="previews-h" className="space-y-2">
          <h2 id="previews-h" className="text-lg font-semibold">
            Free preview lessons
          </h2>
          <p className="text-sm text-muted">Reviewed lessons anyone can read, no sign-in needed.</p>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {d.previews.map((p) => (
              <li key={p.lesson_id} className="px-4 py-3">
                <Link href={`/learn/chapter/${p.chapter_id}#lesson-${p.lesson_id}`} className="font-medium text-accent underline underline-offset-2">
                  {p.title}
                </Link>
                <span className="text-muted">
                  {" "}
                  · {GRADE_LABEL[p.grade]} {p.subject_name} · Chapter {p.chapter_number}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-sm text-muted">{d.plans_note}</p>
    </div>
  );
}
