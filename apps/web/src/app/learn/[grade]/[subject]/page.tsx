import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { getBookFor } from "@/lib/api";
import { GRADE_LABEL, assessmentSummary, chapterHeading, pageRange, parseGrade } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { GlassCardLink } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { StatChip } from "@/components/stat-chip";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";

export const metadata: Metadata = { title: "Chapters" };

export default function BookPage({ params }: PageProps<"/learn/[grade]/[subject]">) {
  return (
    <Suspense fallback={<SkeletonCards count={8} label="Loading chapters" />}>
      {params.then(({ grade, subject }) => (
        <BookView grade={grade} subject={subject} />
      ))}
    </Suspense>
  );
}

async function BookView({ grade: rawGrade, subject }: { grade: string; subject: string }) {
  const grade = parseGrade(rawGrade);
  if (!grade) notFound();
  const res = await getBookFor(grade, subject);
  if (!res.ok) notFound();
  const book = res.data;
  const { breadcrumb: bc } = book;
  const gradeLabel = GRADE_LABEL[bc.grade.number];
  const topics = book.chapters.reduce((n, ch) => n + ch.topic_count, 0);
  const visuals = book.chapters.reduce((n, ch) => n + ch.visual_count, 0);
  const label = bc.chapter_label.toLowerCase();
  return (
    <div data-subject={subjectKey(bc.subject.code)}>
      <Breadcrumbs items={[{ href: "/learn", label: "Learn" }, { label: `${gradeLabel} ${bc.subject.name}` }]} />
      {/* BOOK-PAGE-01 (owner, 2026-10-29: "premium look"): the book opens on a panel in the subject colour, like a
          chapter's opening (CHAPTER-OPENING-01), with what the book holds at a glance. DESIGN-01: now a glass hero. */}
      <PageHero
        align="start"
        className="mb-8"
        accentTitle
        eyebrow={`${gradeLabel} · Punjab textbook`}
        title={bc.subject.name}
        backdrop={
          <>
            <span aria-hidden className="pointer-events-none absolute inset-0 bg-accent-soft opacity-60" />
            <span aria-hidden className="pointer-events-none absolute -bottom-8 right-4 select-none font-display text-[8rem] font-bold leading-none text-accent opacity-10 sm:text-[10rem]">
              {bc.grade.number}
            </span>
          </>
        }
      >
        <div aria-hidden className="-mt-4 mb-4 h-1 w-16 rounded-full bg-accent" />
        <ul className="flex flex-wrap gap-2">
          {(
            [
              ["layers", `${book.chapters.length} ${label}s`],
              ["file-text", `${topics} topics`],
              ["image", `${visuals} figures and tables`],
            ] as const
          ).map(([icon, t]) => (
            <li key={t}>
              <StatChip icon={icon}>{t}</StatChip>
            </li>
          ))}
        </ul>
      </PageHero>
      {book.missing_pages.length > 0 && (
        <div className="mb-6">
          <Notice tone="warn" title="Part of the supplied textbook file is missing">
            {book.missing_pages.join("; ")}. Affected sections are marked below.
          </Notice>
        </div>
      )}
      <ol className="grid gap-4 sm:grid-cols-2">
        {book.chapters.map((ch) => {
          const exercises = assessmentSummary(ch.assessment_counts);
          return (
            <li key={ch.id}>
              <GlassCardLink href={`/learn/chapter/${ch.id}`} padded={false} className="group relative flex h-full gap-4 overflow-hidden p-5">
                <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-accent opacity-0 transition group-hover:opacity-100" />
                <span
                  aria-hidden
                  className="flex size-12 shrink-0 items-center justify-center rounded-inner bg-accent-soft font-display text-xl font-bold text-accent ring-1 ring-accent/20"
                >
                  {ch.number}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-2">
                  <span className="flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
                    <span>
                      {chapterHeading(bc.chapter_label, ch)}
                      {ch.contents_number != null && ch.contents_number !== ch.number && (
                        <span className="normal-case"> · listed as {ch.contents_number} on the Contents page</span>
                      )}
                    </span>
                    {ch.status !== "complete" && <Badge tone="warn">{ch.status}</Badge>}
                  </span>
                  <span className="font-display text-lg leading-snug font-semibold group-hover:text-accent">{ch.title}</span>
                  <span className="mt-auto flex flex-wrap gap-1.5 pt-1 text-xs text-muted">
                    <span className="rounded-full bg-[var(--track)] px-2 py-0.5">{ch.topic_count} topics</span>
                    {ch.visual_count > 0 && <span className="rounded-full bg-[var(--track)] px-2 py-0.5">{ch.visual_count} figures</span>}
                    <span className="rounded-full bg-[var(--track)] px-2 py-0.5">Pages {pageRange(ch.printed_start, ch.printed_end)}</span>
                    {exercises.length > 0 && <span className="rounded-full bg-[var(--track)] px-2 py-0.5">{exercises.slice(0, 2).join(" · ")}</span>}
                  </span>
                </span>
              </GlassCardLink>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
