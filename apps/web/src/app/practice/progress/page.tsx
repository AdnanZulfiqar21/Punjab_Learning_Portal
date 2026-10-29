import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { ProgressReport } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { PracticeIcon } from "@/components/practice-ui";
import { ProgressBar } from "@/components/progress-bar";
import { SectionHeader } from "@/components/section-header";
import { StatChip } from "@/components/stat-chip";
import { Breadcrumbs, Notice, SkeletonCards, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser } from "@/lib/session";
import { PrintButton } from "./print-button";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "Progress report", robots: { index: false } };

const day = (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE }) : "—");

// DESIGN-01: glass panels print as plain bordered boxes.
const PRINT = "print:border-border print:bg-transparent print:shadow-none print:[backdrop-filter:none]";

export default function ProgressPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Progress report" }]} />
      <Suspense
        fallback={
          <div className="space-y-6">
            <SkeletonLines lines={3} label="Preparing your report" />
            <SkeletonCards count={2} label="Preparing your report" />
          </div>
        }
      >
        <Report />
      </Suspense>
    </div>
  );
}

async function Report() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/progress");
  const res = await api<ProgressReport>("/v1/me/progress", { token: user.token });
  if (!res.ok) return <Notice tone="warn" title="Couldn't prepare your report">{res.problem?.detail ?? "Please try again."}</Notice>;
  const r = res.data;
  const tests = r.subjects.reduce((n, s) => n + s.tests, 0);
  const answered = r.subjects.reduce((n, s) => n + s.questions_answered, 0);
  return (
    <article className="space-y-8">
      <PageHero
        align="start"
        className={PRINT}
        eyebrow="Practice · Report"
        title="Progress report"
        lead={
          <span className="block text-sm sm:text-base">
            {user.me.email} · prepared {day(r.generated_at)} · report version {r.report_version}
          </span>
        }
        actions={<PrintButton />}
        backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50 print:hidden" />}
      >
        {r.subjects.length > 0 && (
          <p className="-mt-2 flex flex-wrap gap-2">
            <StatChip icon="list-checks">
              {tests} test{tests === 1 ? "" : "s"}
            </StatChip>
            <StatChip icon="file-text">
              {answered} question{answered === 1 ? "" : "s"} answered
            </StatChip>
            <StatChip>
              <PracticeIcon name="bookmark" size={16} className="text-accent" />
              {r.notebook.open} open in your notebook
            </StatChip>
          </p>
        )}
      </PageHero>
      {r.results_pending > 0 && (
        <Notice title="Results on the way">
          {r.results_pending} submitted scheduled mock{r.results_pending === 1 ? " is" : "s are"} waiting for the release time. They count here once released.
        </Notice>
      )}
      {r.subjects.length === 0 ? (
        r.results_pending === 0 && (
          <Notice title="No submitted tests yet">
            <Link href="/practice" className="font-medium text-accent underline underline-offset-2">
              Take a practice test
            </Link>{" "}
            to start your report.
          </Notice>
        )
      ) : (
        <section aria-labelledby="subjects-h">
          <SectionHeader id="subjects-h" title="By class and subject" />
          <div className={`glass overflow-x-auto rounded-card ${PRINT}`}>
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs tracking-wide text-muted uppercase">
                <tr>
                  {["Class and subject", "Tests", "Answered", "Correct", "Accuracy", "Last activity"].map((h) => (
                    <th key={h} scope="col" className="px-4 py-3 font-semibold">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {r.subjects.map((s) => {
                  const name = `${GRADE_LABEL[s.grade]} ${s.subject.replace("_", " ")}`;
                  return (
                    <tr key={`${s.grade}-${s.subject}`}>
                      <th scope="row" className="px-4 py-3 text-left font-medium capitalize">
                        {name}
                      </th>
                      <td className="px-4 py-3 tabular-nums">{s.tests}</td>
                      <td className="px-4 py-3 tabular-nums">{s.questions_answered}</td>
                      <td className="px-4 py-3 tabular-nums">{s.correct}</td>
                      <td className="min-w-32 px-4 py-3 tabular-nums">
                        {s.accuracy === null ? (
                          "—"
                        ) : (
                          <span className="flex items-center gap-2">
                            <span className="w-10">{`${s.accuracy}%`}</span>
                            <ProgressBar value={s.accuracy} label={`${name} accuracy`} valueText={`${s.accuracy}%`} className="flex-1 print:hidden" />
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">{day(s.last_activity)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {r.recent.length > 0 && (
        <section aria-labelledby="recent-h">
          <SectionHeader id="recent-h" title="Recent results" />
          <ul className={`glass divide-y divide-border overflow-hidden rounded-card text-sm ${PRINT}`}>
            {r.recent.map((t) => (
              <li key={t.attempt_id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
                <span>
                  {day(t.finished_at)} · {t.kind === "mock" ? "Mock" : t.kind === "review" ? "Review" : "Practice"} · {t.parts.map((x) => `${GRADE_LABEL[x.grade]} ${x.subject.replace("_", " ")}`).join(" + ")}
                </span>
                <span className="tabular-nums">
                  <span className="font-semibold">{t.status === "not_scorable" ? "Not scorable" : `${t.raw} / ${t.maximum}${t.percentage === null ? "" : ` (${t.percentage}%)`}`}</span>
                  {t.score_version > 1 && <span className="text-muted"> · updated after review</span>}{" "}
                  <Link
                    href={`/practice/attempt/${t.attempt_id}/result`}
                    className="ml-1 inline-flex min-h-11 items-center px-1 font-medium text-accent underline underline-offset-2 print:hidden"
                  >
                    Open
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <GlassCard as="section" aria-labelledby="nb-h" className={`space-y-3 text-sm ${PRINT}`}>
          <h2 id="nb-h" className="font-display text-lg font-semibold">
            Mistake notebook
          </h2>
          <p>
            {r.notebook.open} open · {r.notebook.mastered} mastered · {r.notebook.voided} withdrawn after review
          </p>
          <Link href="/practice/notebook" className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-2 print:hidden">
            Open your notebook
          </Link>
        </GlassCard>
        <GlassCard as="section" aria-labelledby="def-h" className={`space-y-3 text-sm ${PRINT}`}>
          <h2 id="def-h" className="font-display text-lg font-semibold">
            What these numbers mean
          </h2>
          <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[max-content_1fr]">
            {Object.entries(r.definitions).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="font-medium capitalize">{k.replace("_", " ")}</dt>
                <dd className="text-muted">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-muted">This report counts what you did. It does not say which topics you have mastered.</p>
        </GlassCard>
      </div>
    </article>
  );
}
