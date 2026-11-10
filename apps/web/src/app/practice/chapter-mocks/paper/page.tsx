import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { BookExercises } from "@portal/contracts";
import { MockPaper } from "@/components/mock-paper";
import { PageHero } from "@/components/page-hero";
import { Badge, Breadcrumbs, Notice, SkeletonCards } from "@/components/ui";
import { buildPaper, openTests, PATTERNS } from "@/lib/chapter-mocks";
import { practiceChapters } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = {
  title: "Mock test",
  robots: { index: false },
};

type SetReading = {
  availability: string;
  lesson: {
    body: { blocks: { type: string }[] } | null;
    locked?: boolean;
  } | null;
};

/** CHAPTER-MOCK-01: one chapter mock test, put together from the chapter's own MCQ, short and long question sets. */
export default function MockPaperPage({
  searchParams,
}: PageProps<"/practice/chapter-mocks/paper">) {
  return (
    <Suspense
      fallback={<SkeletonCards count={3} label="Loading the mock test" />}
    >
      {searchParams.then((sp) => {
        const one = (k: string) =>
          typeof sp[k] === "string" ? (sp[k] as string) : "";
        return (
          <Paper
            grade={Number(one("grade"))}
            subject={one("subject")}
            chapter={Number(one("chapter"))}
            n={Number(one("n"))}
          />
        );
      })}
    </Suspense>
  );
}

async function Paper({
  grade,
  subject,
  chapter,
  n,
}: {
  grade: number;
  subject: string;
  chapter: number;
  n: number;
}) {
  const pattern = PATTERNS[subject];
  if (!pattern || !openTests(subject, grade, chapter).includes(n)) notFound();
  const user = await currentUser();
  const opts = user ? { token: user.token } : {};
  const book = await api<BookExercises>(
    `/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/exercises`,
    opts,
  );
  const ch = book.ok
    ? practiceChapters(book.data).find((c) => c.number === chapter)
    : undefined;
  const name = SUBJECTS.find(([c]) => c === subject)?.[1] ?? subject;
  const back = `/practice/chapter-mocks?grade=${grade}&subject=${subject}`;
  const crumbs = (
    <Breadcrumbs
      items={[
        { href: "/practice", label: "Practice" },
        { href: back, label: "Chapter mock tests" },
        { label: `Mock test ${n}` },
      ]}
    />
  );
  if (!book.ok || !ch?.mcqs || !ch.shorts || !ch.longs) {
    return (
      <div className="space-y-6">
        {crumbs}
        <Notice tone="warn" title="This mock test isn't ready">
          {book.ok
            ? "The chapter's practice questions aren't all added yet."
            : (book.problem?.detail ?? "Please try again.")}
        </Notice>
      </div>
    );
  }
  const read = (id: string) => api<SetReading>(`/v1/topics/${id}/lesson`, opts);
  const readings = await Promise.all([
    read(ch.mcqs.topic_id),
    read(ch.shorts.topic_id),
    read(ch.longs.topic_id),
  ]);
  const [mcq, short, long] = readings.map((r) =>
    r.ok && r.data.lesson?.body && !r.data.lesson.locked
      ? r.data.lesson.body.blocks
      : null,
  );
  const draft = readings.some(
    (r) => r.ok && r.data.availability !== "published",
  );
  const label = book.data.chapter_label;
  return (
    <div className="space-y-8" data-subject={subjectKey(subject)}>
      <div>
        {crumbs}
        <PageHero
          align="start"
          eyebrow={`${GRADE_LABEL[grade]} ${name} · ${label} ${chapter}`}
          title={`Mock test ${n}: ${ch.title}`}
          lead="Board paper pattern. Answer the MCQs in the Question paper and submit them; write the short and long answers on paper. The Solution paper shows your MCQ result and a model answer for every part."
          backdrop={
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50"
            />
          }
        />
        {draft && (
          <p className="mt-3">
            <Badge tone="info">Draft preview · under review</Badge>
          </p>
        )}
      </div>
      {!mcq || !short || !long ? (
        <Notice title="Sign in to open this mock test">
          This mock test is still being reviewed. Sign in with a reviewer
          account to see it.
        </Notice>
      ) : (
        <MockPaper
          paper={buildPaper(pattern, chapter, n, { mcq, short, long })}
          head={{
            part: grade === 11 ? "INTERMEDIATE PART-I" : "INTERMEDIATE PART-II",
            className: `Class ${grade === 11 ? "XI" : "XII"}`,
            subject: name.toUpperCase(),
            chapter: `${label} ${chapter}: ${ch.title}`,
          }}
        />
      )}
    </div>
  );
}
