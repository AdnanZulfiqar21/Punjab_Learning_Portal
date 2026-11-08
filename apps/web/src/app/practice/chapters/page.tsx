import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
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

const SUBJECTS = taughtSubjects(ALL_SUBJECTS);

export const metadata: Metadata = { title: "Chapter practice", robots: { index: false } };

const tone = (availability: string): "ok" | "info" | "warn" => (availability === "published" ? "ok" : availability === "private_preview" ? "info" : "warn");

/**
 * PRACTICE-MCQ-01 (owner, 2026-11-08): the portal's own practice questions for every chapter of a book (MCQs now; short
 * and long questions later), by book and then chapter as Learn. Not the book's printed exercises: those stay in Book
 * exercises ("chapter practice ma book exercises kiu dali hain yaha hum khud pure pure book ka mcqs long short sb banaye ga").
 */
export default function ChapterPracticePage({ searchParams }: PageProps<"/practice/chapters">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Chapter practice" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Chapter by chapter"
          title="Chapter practice"
          lead="Our own MCQs and short questions for each chapter of your book, with answers in English and Roman Urdu."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading chapter practice" />}>
        {searchParams.then((sp) => (
          <Chapters grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

/** One question set inside a chapter's card ("MCQs"), with its status; a muted line when it isn't added yet. */
function SetLink({ kind, item }: { kind: string; item?: { topic_id: string; availability: string; available_languages: readonly string[] } }) {
  const base = "flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-inner bg-surface-muted px-4 py-2.5";
  if (!item) {
    return (
      <li className={`${base} text-muted`}>
        <span className="font-semibold">{kind}</span>
        <span className="text-sm">Not added yet</span>
      </li>
    );
  }
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
          className={`${base} text-foreground transition-colors hover:bg-accent-soft hover:text-accent focus-visible:outline-2 focus-visible:outline-accent`}
        >
          {body}
        </Link>
      ) : (
        <span className={`${base} text-muted`}>{body}</span>
      )}
    </li>
  );
}

async function Chapters({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  const profile = user?.me.profile;
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : (profile?.grade ?? 11);
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : (profile?.subjects?.find((s) => SUBJECTS.some(([c]) => c === s)) ?? "computer_science");
  const res = await api<BookExercises>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`, user ? { token: user.token } : {});
  const name = SUBJECTS.find(([c]) => c === subject)?.[1];
  const chapters = res.ok ? practiceChapters(res.data) : [];
  const any = res.ok && ((res.data.mcq_sets ?? []).length > 0 || (res.data.short_sets ?? []).length > 0);
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      <ClassSubjectFilter path="/practice/chapters" grade={grade} subject={subject} subjects={SUBJECTS} />
      {!res.ok ? (
        <Notice tone="warn" title="Couldn't load chapter practice">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : !any ? (
        <Notice title="No chapter practice here yet">
          MCQs and short questions for the {GRADE_LABEL[grade]} {name} book are added chapter by chapter. They appear here once they are.
        </Notice>
      ) : (
        <section aria-labelledby="chapter-practice">
          <SectionHeader id="chapter-practice" title={`${GRADE_LABEL[grade]} ${name}`} description="Every chapter in the book's order." />
          <ol className="grid gap-4 sm:grid-cols-2">
            {chapters.map((ch) => (
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
                    <SetLink kind="MCQs" item={ch.mcqs} />
                    <SetLink kind="Short questions" item={ch.shorts} />
                  </ul>
                </GlassCard>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
