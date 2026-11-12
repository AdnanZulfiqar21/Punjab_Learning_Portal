import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { MockPaper } from "@/components/mock-paper";
import { PageHero } from "@/components/page-hero";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { bookPart, buildBookPaper, partLabel } from "@/lib/book-mocks";
import { PATTERNS } from "@/lib/chapter-mocks";
import { practiceChapters } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { typesetMath } from "@/lib/typeset";

export const metadata: Metadata = {
  title: "Book mock test",
  robots: { index: false },
};

type SetReading = {
  availability: string;
  lesson: { body: { blocks: { type: string }[] } | null; locked?: boolean } | null;
};

/** BOOK-MOCK-01: one full-book or half-book mock test, from the chapters' own MCQ, short and long question sets. */
export default function BookMockPaperPage({ searchParams }: PageProps<"/practice/book-mocks/paper">) {
  return (
    <Suspense fallback={<SkeletonCards count={3} label="Loading the mock test" />}>
      {searchParams.then((sp) => {
        const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
        return <Paper grade={Number(one("grade"))} subject={one("subject")} partKey={one("part")} n={Number(one("n"))} />;
      })}
    </Suspense>
  );
}

async function Paper({ grade, subject, partKey, n }: { grade: number; subject: string; partKey: string; n: number }) {
  const pattern = PATTERNS[subject];
  const found = bookPart(subject, grade, partKey);
  if (!pattern || !found || !Number.isInteger(n) || n < 1 || n > found.part.tests) notFound();
  const { part, half } = found;
  const user = await currentUser();
  const opts = user ? { token: user.token } : {};
  const book = await api<BookExercises>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`, opts);
  const chapters = book.ok
    ? practiceChapters(book.data).filter((c) => c.number >= part.from && c.number <= part.to)
    : [];
  const name = SUBJECTS.find(([c]) => c === subject)?.[1] ?? subject;
  const label = book.ok ? book.data.chapter_label : "Chapter";
  const tab = half ? "half" : "full";
  const back = `/practice/book-mocks?tab=${tab}&book=${subject}-${grade}${half ? `&part=${part.key}` : ""}`;
  const crumbs = (
    <Breadcrumbs
      items={[
        { href: "/practice", label: "Practice" },
        { href: back, label: "Book Mock Test" },
        { label: `Mock test ${n}` },
      ]}
    />
  );
  const ready = chapters.length === part.to - part.from + 1 && chapters.every((c) => c.mcqs && c.shorts && c.longs);
  if (!book.ok || !ready) {
    return (
      <div className="space-y-6">
        {crumbs}
        <Notice tone="warn" title="This mock test isn't ready">
          {book.ok ? "The chapters' practice questions aren't all added yet." : (book.problem?.detail ?? "Please try again.")}
        </Notice>
      </div>
    );
  }
  const read = (id: string) => api<SetReading>(`/v1/topics/${id}/lesson`, opts);
  const readings = await Promise.all(
    chapters.flatMap((c) => [read(c.mcqs!.topic_id), read(c.shorts!.topic_id), read(c.longs!.topic_id)]),
  );
  const blocks = readings.map((r) =>
    r.ok && r.data.lesson?.body && !r.data.lesson.locked ? r.data.lesson.body.blocks : null,
  );
  const draft = readings.some((r) => r.ok && r.data.availability !== "published");
  const sets = chapters.map((_, i) => ({ mcq: blocks[i * 3], short: blocks[i * 3 + 1], long: blocks[i * 3 + 2] }));
  const paper = sets.every((s) => s.mcq && s.short && s.long)
    ? buildBookPaper(
        pattern,
        part,
        n,
        sets.map((s) => ({ mcq: s.mcq!, short: s.short!, long: s.long! })),
      )
    : null;
  const scope = half ? partLabel(part, label) : "Full book";
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      <div>
        {crumbs}
        <PageHero
          align="start"
          eyebrow={`${GRADE_LABEL[grade]} ${name} · ${half ? "Half book" : "Full book"} mock test`}
          title={`Mock test ${n}: ${scope}`}
          lead="Board paper pattern, with questions from every chapter mixed together. Answer the MCQs in the Question paper and submit them; write the short and long answers on paper. The Solution paper shows your MCQ result and a model answer for every part."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
        {draft && (
          <p className="mt-3">
            <Badge tone="info">Draft preview · under review</Badge>
          </p>
        )}
      </div>
      {!paper ? (
        <Notice title="Sign in to open this mock test">
          This mock test is still being reviewed. Sign in with a reviewer account to see it.
        </Notice>
      ) : (
        <MockPaper
          paper={paper}
          math={subject === "mathematics" ? typesetMath(paper) : undefined}
          head={{
            part: grade === 11 ? "INTERMEDIATE PART-I" : "INTERMEDIATE PART-II",
            className: `Class ${grade === 11 ? "XI" : "XII"}`,
            subject: name.toUpperCase(),
            chapter: half ? `${scope} (half book)` : "Full book",
          }}
        />
      )}
    </div>
  );
}
