import type { Metadata } from "next";
import { Suspense } from "react";
import type { BookMistakes } from "@portal/contracts";
import { GlassCard, GlassCardLink } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { PageHero } from "@/components/page-hero";
import { ClassSubjectFilter, PracticeIcon } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { StatChip } from "@/components/stat-chip";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { bookMistakesReady, mistakeCount } from "@/lib/book-mistakes";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS as ALL_SUBJECTS } from "@/lib/practice";
import { taughtSubjects } from "@/lib/practice-filters";
import { api, currentUser } from "@/lib/session";

const SUBJECTS = taughtSubjects(ALL_SUBJECTS);

export const metadata: Metadata = { title: "Book mistakes", robots: { index: false } };

/** BOOK-MISTAKES-01: the errors printed in one textbook. Book (class and subject) → chapter → topic. */
export default function BookMistakesPage({ searchParams }: PageProps<"/practice/book-mistakes">) {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Book mistakes" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · From your textbook"
          title="Book mistakes"
          lead="Errors printed in your textbook, chapter by chapter. Each shows what the book says, marked in red, and the right version in a green box."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonCards count={6} label="Loading book mistakes" />}>
        {searchParams.then((sp) => (
          <Book grade={typeof sp.grade === "string" ? sp.grade : undefined} subject={typeof sp.subject === "string" ? sp.subject : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

async function Book({ grade: rawGrade, subject: rawSubject }: { grade?: string; subject?: string }) {
  const user = await currentUser();
  const grade = rawGrade === "11" || rawGrade === "12" ? Number(rawGrade) : 11;
  const subject = SUBJECTS.some(([c]) => c === rawSubject) ? rawSubject! : "physics";
  const name = SUBJECTS.find(([c]) => c === subject)?.[1];
  const book = `${GRADE_LABEL[grade]} ${name}`;
  const filter = <ClassSubjectFilter path="/practice/book-mistakes" grade={grade} subject={subject} subjects={SUBJECTS} />;
  if (!bookMistakesReady(grade, subject)) {
    return (
      <div className="space-y-8" data-subject={subjectKey(subject)}>
        {filter}
        <Notice title="Being checked">The mistakes of the {book} book are being checked. They appear here once they are.</Notice>
      </div>
    );
  }
  const res = await api<BookMistakes>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/book-mistakes`, user ? { token: user.token } : {});
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      {filter}
      {!res.ok ? (
        <Notice tone="warn" title="Couldn't load the book mistakes">
          {res.problem?.detail ?? "Please try again."}
        </Notice>
      ) : res.data.total === 0 ? (
        <Notice title="Nothing here yet">No printed mistakes of the {book} book can be shown yet.</Notice>
      ) : (
        <section aria-labelledby="book-chapters" className="space-y-5">
          <SectionHeader id="book-chapters" title={book} description="Choose a chapter to see its mistakes, topic by topic." />
          <p className="flex flex-wrap gap-2">
            <StatChip>
              <PracticeIcon name="book-x" size={16} className="text-accent" />
              {mistakeCount(res.data.total)} in this book
            </StatChip>
            <StatChip>
              <Icon name="layers" size={16} className="text-accent" />
              {res.data.chapters.filter((c) => c.count > 0).length} chapters
            </StatChip>
          </p>
          <ol className="grid gap-4 sm:grid-cols-2">
            {res.data.chapters.map((c) => {
              const inner = (
                <>
                  <span
                    aria-hidden="true"
                    className="flex size-12 shrink-0 items-center justify-center rounded-inner bg-accent-soft font-display text-xl font-bold text-accent ring-1 ring-accent/20"
                  >
                    {c.number}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <span className="text-xs font-semibold tracking-wide text-muted uppercase">
                      {res.data.chapter_label} {c.number}
                    </span>
                    <span className={`font-display text-lg leading-snug font-semibold ${c.count ? "text-foreground group-hover:text-accent" : ""}`}>{c.title}</span>
                    <span className="mt-auto flex flex-wrap items-center gap-2 pt-1 text-sm text-muted">
                      {c.count ? (
                        <>
                          <Badge tone="warn">{mistakeCount(c.count)}</Badge>
                          {c.topics.length} {c.topics.length === 1 ? "topic" : "topics"}
                        </>
                      ) : (
                        <Badge tone="ok">No mistakes found</Badge>
                      )}
                    </span>
                  </span>
                </>
              );
              return (
                <li key={c.chapter_id}>
                  {c.count ? (
                    <GlassCardLink href={`/practice/book-mistakes/${c.chapter_id}`} padded={false} className="group flex h-full gap-4 p-5">
                      {inner}
                    </GlassCardLink>
                  ) : (
                    <GlassCard padded={false} className="flex h-full gap-4 p-5 text-muted">
                      {inner}
                    </GlassCard>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      )}
    </div>
  );
}
