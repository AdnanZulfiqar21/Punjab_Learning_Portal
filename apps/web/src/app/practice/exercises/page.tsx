import type { Metadata } from "next";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import type { BookExercises } from "@portal/contracts";
import { GlassCard, GlassCardLink } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { exerciseStatus, practiceChapters } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS as ALL_SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { api, currentUser } from "@/lib/session";

// The book exercises cover the textbooks the portal teaches; Mathematics is not taught (owner, 2026-10-19).
const SUBJECTS = taughtSubjects(ALL_SUBJECTS);

export const metadata: Metadata = { title: "Chapter practice", robots: { index: false } };

const tone = (availability: string): "ok" | "info" | "warn" => (availability === "published" ? "ok" : availability === "private_preview" ? "info" : "warn");

/** BOOK-EXERCISES-01: each chapter's end-of-chapter exercise from the textbook, solved here rather than in Learn.
 * PRACTICE-MCQ-01 (owner, 2026-11-08): Practice by book, then chapter, as Learn; each chapter lists its exercise and MCQs. */
export default function BookExercisesPage({ searchParams }: PageProps<"/practice/exercises">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Chapter practice" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · From your textbook"
          title="Chapter practice"
          lead="Each chapter of your textbook: its end-of-chapter exercise, solved, and MCQs to practise, in English and Roman Urdu."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading chapter practice" />}>
        {searchParams.then((sp) => (
          <Exercises grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

/** One exercise or Board paper as a glass card: a link when it can be opened, a muted card when not. */
function UnitCard({ href, open, children }: { href: string; open: boolean; children: ReactNode }) {
  return open ? (
    <GlassCardLink href={href} padded={false} className="group flex h-full gap-4 p-5">
      {children}
    </GlassCardLink>
  ) : (
    <GlassCard padded={false} className="flex h-full gap-4 p-5 text-muted">
      {children}
    </GlassCard>
  );
}

/** PRACTICE-MCQ-01: one thing to practise inside a chapter's card ("Book exercise", "MCQs"), with its status. */
function PracticeLink({ kind, item }: { kind: string; item: { topic_id: string; availability: string; available_languages: readonly string[] } }) {
  const status = exerciseStatus(item.availability, item.available_languages);
  const body = (
    <>
      <span className="font-semibold">{kind}</span>
      <Badge tone={tone(item.availability)}>{status.label}</Badge>
    </>
  );
  return (
    <li>
      {status.open ? (
        <Link
          href={`/practice/exercises/${item.topic_id}`}
          className="flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-inner bg-surface-muted px-4 py-2.5 text-foreground transition-colors hover:bg-accent-soft hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
        >
          {body}
        </Link>
      ) : (
        <span className="flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-inner bg-surface-muted px-4 py-2.5 text-muted">{body}</span>
      )}
    </li>
  );
}

async function Exercises({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  const profile = user?.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.find((s) => SUBJECTS.some(([c]) => c === s)) ?? "computer_science");
  const res = await api<BookExercises>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`, user ? { token: user.token } : {});
  const name = SUBJECTS.find(([c]) => c === subject)?.[1];
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      <ClassSubjectFilter path="/practice/exercises" grade={grade} subject={subject} subjects={SUBJECTS} />
      {!res.ok ? (
        <Notice tone="warn" title="Couldn't load the book exercises">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : practiceChapters(res.data).length === 0 ? (
        <Notice title="Nothing to practise here yet">
          The exercises and MCQs of the {GRADE_LABEL[grade]} {name} book are added chapter by chapter. They appear here once they are.
        </Notice>
      ) : (
        <section aria-labelledby="chapter-exercises">
          <SectionHeader id="chapter-exercises" title={`${GRADE_LABEL[grade]} ${name}`} description="Every chapter in the book's order, with its exercise and MCQs." />
          <ol className="grid gap-4 sm:grid-cols-2">
            {practiceChapters(res.data).map((ch) => (
              <li key={ch.number}>
                <GlassCard padded={false} className="flex h-full flex-col gap-4 p-5">
                  <span className="flex gap-4">
                    <span
                      aria-hidden="true"
                      className="flex size-12 shrink-0 items-center justify-center rounded-inner bg-accent-soft font-display text-xl font-bold text-accent ring-1 ring-accent/20"
                    >
                      {ch.number}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="text-xs font-semibold tracking-wide text-muted uppercase">
                        {res.data.chapter_label} {ch.number}
                      </span>
                      <h3 className="font-display text-lg leading-snug font-semibold text-foreground">{ch.title}</h3>
                    </span>
                  </span>
                  <ul className="mt-auto grid gap-2">
                    {ch.exercise ? <PracticeLink kind="Book exercise" item={ch.exercise} /> : null}
                    {ch.mcqs ? <PracticeLink kind="MCQs" item={ch.mcqs} /> : null}
                  </ul>
                </GlassCard>
              </li>
            ))}
          </ol>
        </section>
      )}
      {res.ok && res.data.papers.length > 0 && (
        <section id="board-papers-section" aria-labelledby="board-papers" className="scroll-mt-28">
          {/* BOOK-PAPERS-01: the Board's paper pattern and model paper printed at the end of the book, solved. */}
          <SectionHeader id="board-papers" title="Board model paper" description="Printed at the end of the book, solved here." />
          <ol className="grid gap-4 sm:grid-cols-2">
            {res.data.papers.map((p) => {
              const status = exerciseStatus(p.availability, p.available_languages);
              return (
                <li key={p.topic_id}>
                  <UnitCard href={`/practice/exercises/${p.topic_id}`} open={status.open}>
                    <span aria-hidden="true" className="inline-grid size-12 shrink-0 place-items-center rounded-inner bg-accent-soft text-accent ring-1 ring-accent/20">
                      <Icon name="file-text" size={22} />
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                      <span className={`font-display text-lg leading-snug font-semibold ${status.open ? "text-foreground group-hover:text-accent" : ""}`}>{p.title}</span>
                      <span className="mt-auto pt-1">
                        <Badge tone={tone(p.availability)}>{status.label}</Badge>
                      </span>
                    </span>
                  </UnitCard>
                </li>
              );
            })}
          </ol>
        </section>
      )}
    </div>
  );
}
