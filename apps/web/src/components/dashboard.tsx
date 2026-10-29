import Link from "next/link";
import type { Dashboard, Discovery } from "@portal/contracts";
import { ButtonLink } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ProgressBar } from "@/components/progress-bar";
import { SectionHeader } from "@/components/section-header";
import { SubjectTiles } from "@/components/subject-tiles";
import { Notice } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { TIME_ZONE } from "@/lib/dates";

const METER_LABEL: Record<Dashboard["meters"][number]["key"], string> = {
  syllabus_coverage: "Syllabus coverage",
  content_completed: "Content completed",
  demonstrated_knowledge: "Demonstrated knowledge",
};
const subject = (s: string) => s.replace("_", " ");
const when = (s: string) =>
  new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });

/**
 * P11.S1.T2 (DASHBOARD-01): the signed-in home. Every number comes from the API; the three meters stay separate.
 * DESIGN-01 (draft C): opens on the hero with the real "Continue learning" lesson (the last published lesson this
 * learner opened) or "Start learning" when there is none, then the subject tiles; no invented progress anywhere.
 */
export function DashboardView({
  d,
  email,
  studyTools = true,
  books = null,
}: {
  d: Dashboard;
  email: string;
  studyTools?: boolean;
  /** Published books for the subject tiles (DISCOVERY-01); null shows the default subjects. */
  books?: Discovery["books"] | null;
}) {
  const card = "space-y-2";
  const next = d.continue_learning;
  // The learner's own class and subjects when the profile names them; every book otherwise.
  const mine = books && d.profile ? books.filter((b) => b.grade === d.profile!.grade && d.profile!.subjects.includes(b.subject)) : books;
  return (
    <div className="space-y-10">
      <PageHero
        titleId="dashboard-h"
        eyebrow={d.profile ? GRADE_LABEL[d.profile.grade] : "Class 11 · Class 12"}
        title="Your dashboard"
        lead={
          <>
            {email}
            {d.profile && (
              <>
                {" · "}
                <span className="capitalize">{d.profile.subjects.map(subject).join(", ")}</span>
              </>
            )}
          </>
        }
        actions={
          <>
            <ButtonLink href="/learn" variant={next ? "secondary" : "primary"}>
              {next ? "Browse chapters" : "Start learning"}
            </ButtonLink>
            <ButtonLink href="/practice" variant="secondary">
              Practice
            </ButtonLink>
            {studyTools && (
              <ButtonLink href="/study" variant="ghost">
                My study tools
              </ButtonLink>
            )}
          </>
        }
      >
        <GlassCard as="section" aria-labelledby="continue-h" className="mx-auto max-w-xl text-left">
          <h2 id="continue-h" className="font-sans text-sm font-normal text-muted">
            Continue learning
          </h2>
          {next ? (
            <>
              <p className="mt-1 font-display text-xl leading-snug font-semibold">
                <Link href={`/learn/chapter/${next.chapter_id}#lesson-${next.lesson_id}`} className="text-foreground underline-offset-4 hover:text-accent hover:underline">
                  {next.title}
                </Link>
              </p>
              <p className="text-sm text-muted">
                {GRADE_LABEL[next.grade] ?? `Class ${next.grade}`} · <span className="capitalize">{subject(next.subject)}</span> · Chapter{" "}
                {next.chapter_number}: {next.chapter_title}
              </p>
            </>
          ) : (
            <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm">Nothing in progress. Open any lesson and it will appear here.</p>
              <ButtonLink href="/learn">
                Start learning
                <Icon name="arrow-right" size={16} />
              </ButtonLink>
            </div>
          )}
        </GlassCard>
      </PageHero>
      <SubjectTiles books={mine && mine.length > 0 ? mine : books} label="Your subjects" grade={d.profile?.grade ?? undefined} />
      {!d.profile && (
        <Notice title="Choose your class and subjects">
          Your dashboard follows one class at a time.{" "}
          <Link href="/onboarding" className="underline">
            Set up your profile
          </Link>{" "}
          to see your meters and lessons.
        </Notice>
      )}
      {d.unfinished.length > 0 && (
        // P19.S1.T1 (JOURNEYS-01): pick up a test started on any device; its page offers "Continue here".
        <section aria-labelledby="unfinished-h" className="space-y-2">
          <h2 id="unfinished-h" className="font-display text-2xl font-semibold tracking-tight">
            Unfinished tests
          </h2>
          <ul className="glass divide-y divide-border overflow-hidden rounded-card text-sm">
            {d.unfinished.map((u) => (
              <li key={u.attempt_id} className="flex min-h-12 flex-wrap items-center justify-between gap-2 px-5 py-2.5">
                <span>
                  <span className="capitalize">{u.kind}</span> · {GRADE_LABEL[u.grade]} <span className="capitalize">{subject(u.subject)}</span>
                  <span className="block text-xs text-muted">
                    {u.answered !== null && u.questions !== null ? `${u.answered} of ${u.questions} answered` : "Pages not submitted yet"}
                    {u.closes_at ? ` · closes ${when(u.closes_at)}` : ""}
                  </span>
                </span>
                <Link
                  href={u.kind === "written" ? `/practice/written/${u.attempt_id}` : `/practice/attempt/${u.attempt_id}`}
                  className="font-medium text-accent underline underline-offset-2"
                  aria-label={`Continue ${u.kind} test, ${GRADE_LABEL[u.grade]} ${subject(u.subject)}`}
                >
                  Continue
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <GlassCard as="section" aria-labelledby="revision-h" className={card}>
          <h2 id="revision-h" className="font-display text-lg font-semibold">
            Today&apos;s revision
          </h2>
          <p className="text-sm">
            {d.revision.due === 0
              ? "Nothing due today."
              : `${d.revision.due} mistake${d.revision.due === 1 ? "" : "s"} due for review.`}{" "}
            <span className="text-muted">{d.revision.open} open in your notebook.</span>
          </p>
          <Link href="/practice/notebook" className="text-sm text-accent underline underline-offset-2">
            Open notebook
          </Link>
        </GlassCard>
        <GlassCard as="section" aria-labelledby="mock-h" className={card}>
          <h2 id="mock-h" className="font-display text-lg font-semibold">
            Upcoming mock
          </h2>
          {d.upcoming_mock ? (
            <p className="text-sm">
              <span className="font-medium">{d.upcoming_mock.title}</span>
              <br />
              <span className="text-muted">
                {d.upcoming_mock.state === "upcoming"
                  ? `Starts ${when(d.upcoming_mock.starts_at)}`
                  : `Open until ${when(d.upcoming_mock.entry_closes_at)}`}{" "}
                (Pakistan time)
              </span>
              <br />
              <Link href="/practice/mocks" className="text-accent underline underline-offset-2">
                Scheduled mocks
              </Link>
            </p>
          ) : (
            <p className="text-sm text-muted">No mock is scheduled.</p>
          )}
        </GlassCard>
      </div>
      <section aria-labelledby="meters-h" className="space-y-3">
        <SectionHeader id="meters-h" title="Progress" description="Three separate measures. They are never combined into one score." className="mb-0" />
        <ul className="grid gap-4 sm:grid-cols-3">
          {d.meters.map((m) => (
            <GlassCard as="li" key={m.key} className={card}>
              <h3 className="font-medium">{METER_LABEL[m.key]}</h3>
              {m.percent === null ? (
                <>
                  <p className="font-display text-2xl font-semibold text-muted">Unavailable</p>
                  <p className="text-sm">{m.unavailable}</p>
                </>
              ) : (
                <>
                  <p className="font-display text-3xl font-semibold tabular-nums">{m.percent}%</p>
                  <ProgressBar value={m.percent} label={METER_LABEL[m.key]} valueText={`${m.percent}%, ${m.numerator} of ${m.denominator}`} />
                  <p className="text-sm tabular-nums text-muted">
                    {m.numerator} of {m.denominator}
                  </p>
                </>
              )}
              <p className="text-xs text-muted">{m.definition}</p>
            </GlassCard>
          ))}
        </ul>
      </section>
      <section aria-labelledby="recent-h" className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="recent-h" className="font-display text-2xl font-semibold tracking-tight">
            Recent results
          </h2>
          <Link href="/practice/progress" className="text-sm text-accent underline underline-offset-2">
            Full progress report
          </Link>
        </div>
        {d.results_pending > 0 && (
          <p className="text-sm">
            {d.results_pending} scheduled mock result{d.results_pending === 1 ? " is" : "s are"} waiting for release.
          </p>
        )}
        {d.recent.length === 0 ? (
          <p className="text-sm text-muted">
            No submitted tests yet.{" "}
            <Link href="/practice" className="underline">
              Take a practice test
            </Link>
          </p>
        ) : (
          <ul className="glass divide-y divide-border overflow-hidden rounded-card text-sm">
            {d.recent.map((t) => (
              <li key={t.attempt_id} className="flex min-h-12 flex-wrap items-center justify-between gap-2 px-5 py-2.5">
                <span className="capitalize">
                  {t.kind === "mock" ? "Mock" : t.kind === "review" ? "Review" : "Practice"} ·{" "}
                  {t.parts.map((x) => `${GRADE_LABEL[x.grade]} ${subject(x.subject)}`).join(" + ")}
                </span>
                <span className="tabular-nums">
                  {t.status === "not_scorable"
                    ? "Not scorable"
                    : `${t.raw} / ${t.maximum}${t.percentage === null ? "" : ` (${t.percentage}%)`}`}{" "}
                  <Link href={`/practice/attempt/${t.attempt_id}/result`} className="text-accent underline underline-offset-2">
                    Open
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
