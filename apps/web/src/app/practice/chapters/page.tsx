import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { GlassCard } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { exerciseStatus, practiceChapters } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS as ALL_SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

// PRACTICE-MATHS-01 (owner, 2026-11-10): Mathematics 11 has chapter practice too (Board-style MCQs, short and long
// questions per unit), so this page offers every subject; Book exercises and the other Practice pages keep their filters.
const SUBJECTS: [string, string][] = ALL_SUBJECTS.map(([code, name]) => [code, name]);

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
          lead="Our own MCQs, short questions and long questions for each chapter of your book, with answers in English and Roman Urdu."
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
  const any = res.ok && [res.data.mcq_sets, res.data.short_sets, res.data.long_sets].some((s) => (s ?? []).length > 0);
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      <ClassSubjectFilter path="/practice/chapters" grade={grade} subject={subject} subjects={SUBJECTS} />
      {!res.ok ? (
        <Notice tone="warn" title="Couldn't load chapter practice">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : !any ? (
        <Notice title="No chapter practice here yet">
          MCQs, short questions and long questions for the {GRADE_LABEL[grade]} {name} book are added chapter by chapter. They appear here once they are.
        </Notice>
      ) : (
        <section aria-labelledby="chapter-practice">
          <SectionHeader id="chapter-practice" title={`${GRADE_LABEL[grade]} ${name}`} description="Every chapter in the book's order." />
          {/* PRACTICE-ACCORDION-01 (owner, 2026-11-10): each chapter is a fold like the phone's contents menu; tapping it
              shows its MCQs, Short questions and Long questions. */}
          {/* PRACTICE-COLUMNS-01 (owner, 2026-11-10): two independent columns (odd chapters left, even right) so an open
              fold pushes down only the chapters under it and never leaves a gap beside it. On a phone the two lists
              dissolve (display: contents) into one column ordered 1, 2, 3 ... by `order`. */}
          <div className="flex flex-col gap-4 sm:grid sm:grid-cols-2 sm:items-start">
            {[0, 1].map((col) => (
              <ol key={col} className="contents sm:flex sm:flex-col sm:gap-4">
                {chapters.map((ch, i) => {
                  if (i % 2 !== col) return null;
                  const sets = [ch.mcqs, ch.shorts, ch.longs].filter(Boolean).length;
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
                                {res.data.chapter_label} {ch.number}
                              </span>
                              <h3 className="font-display text-lg leading-snug font-semibold text-foreground">{ch.title}</h3>
                            </span>
                            <span className="flex shrink-0 items-center gap-1 text-sm text-muted">
                              <span aria-label={`${sets} question sets`}>{sets}</span>
                              <Icon name="chevron-right" size={18} className="transition-transform duration-200 group-open:rotate-90" />
                            </span>
                          </summary>
                          <ul className="grid gap-2 px-5 pb-5">
                            <SetLink kind="MCQs" item={ch.mcqs} />
                            <SetLink kind="Short questions" item={ch.shorts} />
                            <SetLink kind="Long questions" item={ch.longs} />
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
