import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { getBookFor } from "@/lib/api";
import { GRADE_LABEL, assessmentSummary, chapterHeading, pageRange, parseGrade } from "@/lib/format";
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
  return (
    <div>
      <Breadcrumbs items={[{ href: "/learn", label: "Learn" }, { label: `${gradeLabel} ${bc.subject.name}` }]} />
      <header className="mb-6 space-y-2">
        <p className="text-sm font-medium text-accent">{gradeLabel}</p>
        <h1 className="text-2xl font-semibold tracking-tight">{bc.subject.name}</h1>
        <p className="text-muted">
          {book.chapters.length} {bc.chapter_label.toLowerCase()}s · textbook source {bc.source_id}
        </p>
      </header>
      {book.missing_pages.length > 0 && (
        <div className="mb-6">
          <Notice tone="warn" title="Part of the supplied textbook file is missing">
            {book.missing_pages.join("; ")}. Affected sections are marked below.
          </Notice>
        </div>
      )}
      <ol className="grid gap-3 sm:grid-cols-2">
        {book.chapters.map((ch) => {
          const exercises = assessmentSummary(ch.assessment_counts);
          return (
            <li key={ch.id}>
              <Link
                href={`/learn/chapter/${ch.id}`}
                className="flex h-full flex-col gap-2 rounded-xl border border-border bg-surface p-4 hover:border-accent"
              >
                <span className="flex items-center justify-between gap-2 text-sm text-muted">
                  <span>
                    {chapterHeading(bc.chapter_label, ch)}
                    {ch.contents_number != null && ch.contents_number !== ch.number && (
                      <span> · listed as {ch.contents_number} on the Contents page</span>
                    )}
                  </span>
                  {ch.status !== "complete" && <Badge tone="warn">{ch.status}</Badge>}
                </span>
                <span className="font-medium">{ch.title}</span>
                <span className="mt-auto text-xs text-muted">
                  {ch.topic_count} topics · {ch.visual_count} figures/tables · book pages{" "}
                  {pageRange(ch.printed_start, ch.printed_end)}
                  {exercises.length > 0 && <> · {exercises.slice(0, 2).join(", ")}</>}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
