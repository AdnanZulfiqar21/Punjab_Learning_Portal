import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import type { BookExercises } from "@portal/contracts";
import { GlassCard, GlassCardLink } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { exerciseStatus } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS as ALL_SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { api, currentUser } from "@/lib/session";

// The book exercises cover the textbooks the portal teaches; Mathematics is not taught (owner, 2026-10-19).
const SUBJECTS = taughtSubjects(ALL_SUBJECTS);

export const metadata: Metadata = { title: "Book exercises", robots: { index: false } };

const tone = (availability: string): "ok" | "info" | "warn" => (availability === "published" ? "ok" : availability === "private_preview" ? "info" : "warn");

/** BOOK-EXERCISES-01: each chapter's end-of-chapter exercise from the textbook, solved here rather than in Learn. */
export default function BookExercisesPage({ searchParams }: PageProps<"/practice/exercises">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Book exercises" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · From your textbook"
          title="Book exercises"
          lead="The exercise at the end of each chapter of your textbook, solved in English and Roman Urdu."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading book exercises" />}>
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
      ) : res.data.exercises.length === 0 ? (
        <Notice title="No book exercises here yet">
          The end-of-chapter exercises of the {GRADE_LABEL[grade]} {name} book are added chapter by chapter. They appear here once they are.
        </Notice>
      ) : (
        <section aria-labelledby="chapter-exercises">
          <SectionHeader id="chapter-exercises" title={`${GRADE_LABEL[grade]} ${name}`} description="The exercise of each chapter, in the book's order." />
          <ol className="grid gap-4 sm:grid-cols-2">
            {res.data.exercises.map((e) => {
              const status = exerciseStatus(e.availability, e.available_languages);
              return (
                <li key={e.topic_id}>
                  <UnitCard href={`/practice/exercises/${e.topic_id}`} open={status.open}>
                    <span
                      aria-hidden="true"
                      className="flex size-12 shrink-0 items-center justify-center rounded-inner bg-accent-soft font-display text-xl font-bold text-accent ring-1 ring-accent/20"
                    >
                      {e.chapter_number}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                      <span className="text-xs font-semibold tracking-wide text-muted uppercase">
                        {res.data.chapter_label} {e.chapter_number}
                      </span>
                      <span className={`font-display text-lg leading-snug font-semibold ${status.open ? "text-foreground group-hover:text-accent" : ""}`}>
                        {e.chapter_title}
                      </span>
                      <span className="mt-auto pt-1">
                        <Badge tone={tone(e.availability)}>{status.label}</Badge>
                      </span>
                    </span>
                  </UnitCard>
                </li>
              );
            })}
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
