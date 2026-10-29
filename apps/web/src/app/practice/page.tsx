import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import { ButtonLink } from "@/components/button";
import { GlassCard, GlassCardLink } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter, IconTile, PracticeIcon } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { Notice, SkeletonCards, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { getAvailability, SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { currentUser } from "@/lib/session";
import { getAccess } from "@/lib/access";
import { PlanStatus } from "@/components/plan-status";
import { PracticeBuilder } from "./practice-builder";

export const metadata: Metadata = { title: "Practice", robots: { index: false } };

// DESIGN-01: Practice offers only the subjects the portal teaches (Mathematics is not taught, owner 2026-10-19).
const TAUGHT = taughtSubjects(SUBJECTS);

type Way = { href: string; title: string; text: string; icon: ReactNode };

// The other ways to practise, each a page of its own. What each one is, in the words of its page; no figures.
const WAYS: Way[] = [
  { href: "/practice/written", title: "Written practice", text: "Answer on paper, photograph your pages, teacher-marked.", icon: <PracticeIcon name="pen-line" size={22} /> },
  { href: "/practice/mocks", title: "Mock tests", text: "Full-length tests that follow official patterns.", icon: <PracticeIcon name="timer" size={22} /> },
  { href: "/practice/notebook", title: "Mistake notebook", text: "Questions you missed or flagged come back for review.", icon: <PracticeIcon name="bookmark" size={22} /> },
  { href: "/practice/progress", title: "Progress report", text: "Your tests, answers and results, ready to print.", icon: <PracticeIcon name="trending-up" size={22} /> },
  { href: "/practice/evidence", title: "What you've shown", text: "Each topic judged from your recent answers.", icon: <PracticeIcon name="circle-check" size={22} /> },
  { href: "/practice/plan", title: "Study plan", text: "One book up to your target date, weakest topics first.", icon: <PracticeIcon name="calendar" size={22} /> },
];

export default function PracticePage({ searchParams }: PageProps<"/practice">) {
  return (
    <div className="space-y-12">
      <PageHero
        eyebrow="Class 11 · Class 12"
        title="Practice"
        lead="Build a test from chapters of your textbook. Only questions approved by an independent subject reviewer are used."
        actions={
          <>
            <ButtonLink href="#build" size="lg">
              Build a test
              <Icon name="arrow-right" size={18} />
            </ButtonLink>
            <ButtonLink href="/practice/exercises" variant="secondary" size="lg">
              <Icon name="book-open" size={18} />
              Book exercises
            </ButtonLink>
          </>
        }
      />

      <section aria-labelledby="ways-heading">
        <SectionHeader id="ways-heading" title="Ways to practise" />
        <div className="grid gap-4 lg:grid-cols-3">
          {/* BOOK-EXERCISES-01 / BOOK-PAPERS-01: the textbook's own exercises and Board paper, solved, lead the list. */}
          <GlassCardLink href="/practice/exercises" padded={false} className="group relative flex flex-col gap-4 overflow-hidden p-6 lg:col-span-2 sm:p-7">
            <span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />
            <span className="relative flex items-start gap-4">
              <IconTile size={52}>
                <Icon name="book-open" size={26} />
              </IconTile>
              <span className="min-w-0 space-y-1.5">
                <span className="block text-xs font-semibold tracking-[0.15em] text-accent uppercase">From your textbook</span>
                <h3 className="font-display text-2xl leading-tight font-semibold group-hover:text-accent">Book exercises</h3>
                <span className="block text-[15px] text-muted">Each chapter&apos;s exercise, solved, in English and Roman Urdu.</span>
              </span>
            </span>
            <span className="relative mt-auto inline-flex items-center gap-1.5 text-sm font-semibold text-accent">
              Open the exercises
              <Icon name="arrow-right" size={16} />
            </span>
          </GlassCardLink>
          <GlassCardLink href="/practice/exercises#board-papers-section" className="group flex flex-col gap-3">
            <IconTile>
              <Icon name="file-text" size={22} />
            </IconTile>
            <h3 className="font-display text-lg font-semibold group-hover:text-accent">Board model paper</h3>
            <span className="text-[15px] text-muted">The Board&apos;s paper pattern and model paper printed at the end of your book.</span>
          </GlassCardLink>
        </div>
        <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {WAYS.map((w) => (
            <li key={w.href}>
              <GlassCardLink href={w.href} className="group flex h-full items-start gap-4">
                <span aria-hidden="true" className="inline-grid size-11 shrink-0 place-items-center rounded-inner bg-accent-soft text-accent ring-1 ring-accent/20">
                  {w.icon}
                </span>
                <span className="min-w-0 space-y-1">
                  <h3 className="font-display text-lg leading-snug font-semibold group-hover:text-accent">{w.title}</h3>
                  <span className="block text-sm text-muted">{w.text}</span>
                </span>
              </GlassCardLink>
            </li>
          ))}
        </ul>
      </section>

      <section id="build" aria-labelledby="build-heading" className="scroll-mt-28">
        <SectionHeader
          id="build-heading"
          title="Build a practice test"
          description="Choose a class and subject, then the chapters to cover."
        />
        <Suspense
          fallback={
            <div className="space-y-4">
              <SkeletonCards count={2} label="Loading practice options" />
              <SkeletonLines lines={6} label="Loading chapters" />
            </div>
          }
        >
          {searchParams.then((sp) => (
            <Builder grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
          ))}
        </Suspense>
      </section>
    </div>
  );
}

async function Builder({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice");
  const profile = user.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.[0] ?? "biology");
  const [availability, access] = await Promise.all([getAvailability(user.token, grade, subject), getAccess(user.token)]);
  const total = availability?.chapters.reduce((n, c) => n + c.questions, 0) ?? 0;
  return (
    <div className="space-y-6">
      <ClassSubjectFilter path="/practice" grade={grade} subject={subject} subjects={TAUGHT} />
      {access && <PlanStatus access={access} purpose="Practice tests" />}
      {access && !access.has_access ? null : !availability || total === 0 ? (
        <Notice title="No approved practice questions yet">
          Questions for {GRADE_LABEL[grade]} {SUBJECTS.find(([c]) => c === subject)?.[1]} appear here once a subject reviewer approves
          them and they are published. Nothing unreviewed is ever used in a test.
        </Notice>
      ) : (
        <GlassCard className="sm:p-7">
          <PracticeBuilder
            grade={grade}
            subject={subject}
            chapters={availability.chapters}
            subjects={TAUGHT}
            secondsPerQuestion={availability.seconds_per_question ?? null}
            estimateBasedOn={availability.estimate_based_on ?? 0}
          />
        </GlassCard>
      )}
    </div>
  );
}
