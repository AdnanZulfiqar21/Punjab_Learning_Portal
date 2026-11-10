import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { openTests, PATTERNS, TESTS_PER_CHAPTER } from "@/lib/chapter-mocks";
import { practiceChapters } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS as ALL_SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

const SUBJECTS: [string, string][] = ALL_SUBJECTS.map(([code, name]) => [code, name]);

export const metadata: Metadata = { title: "Chapter mock tests", robots: { index: false } };

/**
 * CHAPTER-MOCK-01 (owner, 2026-11-10): mock tests chapter by chapter, laid out as Chapter practice ("jasy chapter
 * practice dale the wasy he ... mock test 1 2 3"). Each test is a full Board-pattern paper with a Question paper and a
 * Solution paper. Only the tests in OPEN are offered while the owner checks the first one.
 */
export default function ChapterMocksPage({ searchParams }: PageProps<"/practice/chapter-mocks">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Chapter mock tests" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Board paper pattern"
          title="Chapter mock tests"
          lead="A full paper for each chapter in the Board pattern: answer the MCQs here, write the short and long answers, then check them in the Solution paper."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading mock tests" />}>
        {searchParams.then((sp) => (
          <Chapters grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

async function Chapters({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  const profile = user?.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.find((s) => SUBJECTS.some(([c]) => c === s)) ?? "physics");
  const name = SUBJECTS.find(([c]) => c === subject)?.[1];
  const res = PATTERNS[subject] ? await api<BookExercises>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`, user ? { token: user.token } : {}) : null;
  const chapters = res?.ok ? practiceChapters(res.data) : [];
  const label = res?.ok ? res.data.chapter_label : "Chapter";
  const any = chapters.some((ch) => openTests(subject, grade, ch.number).length > 0);
  const base = "flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-inner bg-surface-muted px-4 py-2.5";
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      <ClassSubjectFilter path="/practice/chapter-mocks" grade={grade} subject={subject} subjects={SUBJECTS} />
      {res && !res.ok ? (
        <Notice tone="warn" title="Couldn't load the mock tests">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : !any ? (
        <Notice title="No mock tests here yet">
          Mock tests for the {GRADE_LABEL[grade]} {name} book are added chapter by chapter. They appear here once they are.
        </Notice>
      ) : (
        <section aria-labelledby="chapter-mocks">
          <SectionHeader id="chapter-mocks" title={`${GRADE_LABEL[grade]} ${name}`} description="Every chapter in the book's order." />
          <div className="flex flex-col gap-4 sm:grid sm:grid-cols-2 sm:items-start">
            {[0, 1].map((col) => (
              <ol key={col} className="contents sm:flex sm:flex-col sm:gap-4">
                {chapters.map((ch, i) => {
                  if (i % 2 !== col) return null;
                  const open = openTests(subject, grade, ch.number);
                  return (
                    <li key={ch.number} style={{ order: i }}>
                      <GlassCard padded={false} className="p-0">
                        <details className="outline-fold group">
                          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-4 rounded-[inherit] p-5 focus-visible:outline-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden">
                            <span
                              aria-hidden="true"
                              className="flex size-12 shrink-0 items-center justify-center rounded-inner bg-accent-soft font-display text-xl font-bold text-accent ring-1 ring-accent/20"
                            >
                              {ch.number}
                            </span>
                            <span className="flex min-w-0 flex-1 flex-col gap-1">
                              <span className="text-xs font-semibold tracking-wide text-muted uppercase">
                                {label} {ch.number}
                              </span>
                              <h3 className="font-display text-lg leading-snug font-semibold text-foreground">{ch.title}</h3>
                            </span>
                            <span className="flex shrink-0 items-center gap-1 text-sm text-muted">
                              <span aria-label={`${open.length} mock tests`}>{open.length}</span>
                              <Icon name="chevron-right" size={18} className="transition-transform duration-200 group-open:rotate-90" />
                            </span>
                          </summary>
                          <ul className="grid gap-2 px-5 pb-5">
                            {Array.from({ length: TESTS_PER_CHAPTER }, (_, k) => k + 1).map((n) =>
                              open.includes(n) ? (
                                <li key={n}>
                                  <Link
                                    href={`/practice/chapter-mocks/paper?grade=${grade}&subject=${subject}&chapter=${ch.number}&n=${n}`}
                                    className={`${base} text-foreground transition-colors hover:bg-accent-soft hover:text-accent focus-visible:outline-2 focus-visible:outline-accent`}
                                  >
                                    <span className="font-semibold">Mock test {n}</span>
                                    <span className="text-sm">Question paper · Solution paper</span>
                                  </Link>
                                </li>
                              ) : (
                                <li key={n} className={`${base} text-muted`}>
                                  <span className="font-semibold">Mock test {n}</span>
                                  <span className="text-sm">Not added yet</span>
                                </li>
                              ),
                            )}
                          </ul>
                        </details>
                      </GlassCard>
                    </li>
                  );
                })}
              </ol>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
