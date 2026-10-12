import Link from "next/link";
import type { Dashboard } from "@portal/contracts";
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

/** P11.S1.T2 (DASHBOARD-01): the signed-in home. Every number comes from the API; the three meters stay separate. */
export function DashboardView({ d, email, studyTools = true }: { d: Dashboard; email: string; studyTools?: boolean }) {
  const card = "space-y-2 rounded-xl border border-border bg-surface p-4";
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your dashboard</h1>
        <p className="text-sm text-muted">
          {email}
          {d.profile && (
            <>
              {" · "}
              {GRADE_LABEL[d.profile.grade]} · <span className="capitalize">{d.profile.subjects.map(subject).join(", ")}</span>
            </>
          )}
        </p>
        </div>
        {studyTools && (
          <Link href="/study" className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm hover:border-accent">
            My study tools
          </Link>
        )}
      </div>
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
          <h2 id="unfinished-h" className="text-lg font-semibold">
            Unfinished tests
          </h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {d.unfinished.map((u) => (
              <li key={u.attempt_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
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
      <div className="grid gap-4 sm:grid-cols-3">
        <section aria-labelledby="continue-h" className={card}>
          <h2 id="continue-h" className="font-semibold">
            Continue learning
          </h2>
          {d.continue_learning ? (
            <p className="text-sm">
              <Link
                href={`/learn/chapter/${d.continue_learning.chapter_id}#lesson-${d.continue_learning.lesson_id}`}
                className="font-medium text-accent underline underline-offset-2"
              >
                {d.continue_learning.title}
              </Link>
              <br />
              <span className="text-muted">
                Chapter {d.continue_learning.chapter_number}: {d.continue_learning.chapter_title}
              </span>
            </p>
          ) : (
            <p className="text-sm text-muted">
              Nothing in progress.{" "}
              <Link href="/learn" className="underline">
                Browse chapters
              </Link>
            </p>
          )}
        </section>
        <section aria-labelledby="revision-h" className={card}>
          <h2 id="revision-h" className="font-semibold">
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
        </section>
        <section aria-labelledby="mock-h" className={card}>
          <h2 id="mock-h" className="font-semibold">
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
        </section>
      </div>
      <section aria-labelledby="meters-h" className="space-y-3">
        <h2 id="meters-h" className="text-lg font-semibold">
          Progress
        </h2>
        <p className="text-sm text-muted">Three separate measures. They are never combined into one score.</p>
        <ul className="grid gap-4 sm:grid-cols-3">
          {d.meters.map((m) => (
            <li key={m.key} className={card}>
              <h3 className="font-medium">{METER_LABEL[m.key]}</h3>
              {m.percent === null ? (
                <>
                  <p className="text-2xl font-semibold text-muted">Unavailable</p>
                  <p className="text-sm">{m.unavailable}</p>
                </>
              ) : (
                <>
                  <p className="text-2xl font-semibold tabular-nums">{m.percent}%</p>
                  <div className="h-2 overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
                    <div className="h-full rounded-full bg-accent" style={{ width: `${m.percent}%` }} />
                  </div>
                  <p className="text-sm tabular-nums text-muted">
                    {m.numerator} of {m.denominator}
                  </p>
                </>
              )}
              <p className="text-xs text-muted">{m.definition}</p>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="recent-h" className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="recent-h" className="text-lg font-semibold">
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
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {d.recent.map((t) => (
              <li key={t.attempt_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
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
