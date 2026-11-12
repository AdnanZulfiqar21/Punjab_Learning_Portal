import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { BookMistakes, BookMistakeTopic } from "@portal/contracts";
import { Icon } from "@/components/icons";
import { LessonBlocks } from "@/components/lesson-blocks";
import { PracticeIcon } from "@/components/practice-ui";
import { StatChip } from "@/components/stat-chip";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { chapterVerified, mistakeCount, topicHref } from "@/lib/book-mistakes";
import { premiumBook } from "@/lib/book-style";
import { GRADE_LABEL } from "@/lib/format";
import { subjectKey } from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";
import { solvedLabels } from "@/lib/solved-labels";
import { typesetEquations, typesetMath } from "@/lib/typeset";

export const metadata: Metadata = { title: "Book mistakes", robots: { index: false } };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** BOOK-MISTAKES-01: one chapter's printed mistakes, topic by topic, drawn as the English lesson draws them. */
export default function ChapterMistakesPage({ params }: PageProps<"/practice/book-mistakes/[chapterId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={10} label="Loading the chapter's mistakes" />}>
      {params.then(({ chapterId }) => (
        <Chapter id={chapterId} />
      ))}
    </Suspense>
  );
}

async function Chapter({ id }: { id: string }) {
  if (!UUID.test(id)) notFound();
  const user = await currentUser();
  const res = await api<BookMistakes>(`/v1/chapters/${id}/book-mistakes`, user ? { token: user.token } : {});
  if (!res.ok) notFound();
  const book = res.data;
  const chapter = book.chapters[0];
  if (!chapter || !chapterVerified(book.grade_number, book.subject_code, chapter.number)) notFound();
  const subject = subjectKey(book.subject_name);
  const bookName = `${GRADE_LABEL[book.grade_number] ?? `Class ${book.grade_number}`} ${book.subject_name}`;
  const back = `/practice/book-mistakes?grade=${book.grade_number}&subject=${book.subject_code}`;
  return (
    <article className="mx-auto max-w-3xl space-y-8" data-subject={subject}>
      <div className="space-y-4">
        <Breadcrumbs
          items={[
            { href: "/practice", label: "Practice" },
            { href: back, label: `Book mistakes · ${bookName}` },
            { label: `${book.chapter_label} ${chapter.number}` },
          ]}
        />
        <header className="glass space-y-3 rounded-card px-6 py-6 sm:px-8 sm:py-7">
          <p className="text-xs font-semibold tracking-[0.15em] text-accent uppercase">
            {bookName} · {book.chapter_label} {chapter.number}
          </p>
          <h1 className="font-display text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">{chapter.title}</h1>
          <p className="text-muted">
            What the book prints is marked in red; the green box below it gives the right version. Each one has been checked
            against the printed page.
          </p>
          <p className="flex flex-wrap gap-2 pt-1">
            <StatChip>
              <PracticeIcon name="book-x" size={16} className="text-accent" />
              {mistakeCount(chapter.count)}
            </StatChip>
            <StatChip>
              <Icon name="list-checks" size={16} className="text-accent" />
              {chapter.topics.length} {chapter.topics.length === 1 ? "topic" : "topics"}
            </StatChip>
          </p>
        </header>
      </div>

      {chapter.topics.length === 0 ? (
        <Notice title="No mistakes found">No printed mistakes are marked in this chapter.</Notice>
      ) : (
        <>
          <nav aria-label="Topics with mistakes" className="glass rounded-card px-4 py-3 sm:px-5">
            <ul className="flex flex-wrap gap-2">
              {chapter.topics.map((t) => (
                <li key={t.topic_id}>
                  <a
                    href={`#t-${t.topic_id}`}
                    className="inline-flex min-h-11 items-center gap-2 rounded-full border border-border bg-surface/70 px-4 text-sm hover:border-accent hover:text-accent"
                  >
                    {topicLabel(t)}
                    <span className="text-xs text-muted">{t.count}</span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          {chapter.topics.map((t) => (
            <TopicMistakes key={t.topic_id} topic={t} premium={premiumBook(subject, book.grade_number)} />
          ))}
        </>
      )}
    </article>
  );
}

// An excerpt has no text for a side figure or a short printed box to sit beside: draw them across the width.
const alone = (b: Record<string, unknown>) => (b.type === "diagram" ? { ...b, side: false } : b.type === "callout" ? { ...b, wide: true } : b);

const topicLabel = (t: BookMistakeTopic) => (t.practice_only ? "Exercise" : [t.number, t.title].filter(Boolean).join(" "));

function TopicMistakes({ topic, premium }: { topic: BookMistakeTopic; premium: boolean }) {
  const assetUrl = (versionId: string) =>
    topic.availability === "private_preview" ? `/learn/topics/${topic.topic_id}/preview-assets/${versionId}` : `/learn/lessons/${topic.lesson_id}/assets/${versionId}`;
  return (
    <section id={`t-${topic.topic_id}`} aria-labelledby={`h-${topic.topic_id}`} className="scroll-mt-24 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border pb-2">
        <h2 id={`h-${topic.topic_id}`} className="font-display text-xl font-semibold tracking-tight sm:text-2xl">
          {topic.practice_only ? topic.title : topicLabel(topic)}
        </h2>
        <span className="flex items-center gap-3 text-sm">
          {topic.availability === "private_preview" && <Badge tone="info">Draft preview</Badge>}
          <Link href={topicHref(topic)} className="inline-flex min-h-11 items-center gap-1 font-semibold text-accent underline-offset-4 hover:underline">
            Open topic
            <Icon name="arrow-right" size={16} />
          </Link>
        </span>
      </div>
      {topic.locked ? (
        <Notice title={mistakeCount(topic.count)}>This topic is part of the full book. Start your plan or trial to read it.</Notice>
      ) : (
        <ol className="space-y-4">
          {topic.mistakes.map((m, i) => {
            const blocks = [...m.context.map(alone), ...m.corrections] as { type: string }[];
            return (
              <li key={i} className="space-y-2 rounded-card border border-border bg-surface px-4 py-4 text-[1.0625rem] leading-7 shadow-glass sm:px-6 sm:py-5" lang="en">
                <p className="text-xs font-semibold tracking-wide text-muted uppercase">Mistake {i + 1}</p>
                <LessonBlocks
                  blocks={blocks}
                  typeset={typesetEquations(blocks)}
                  math={typesetMath(blocks)}
                  premium={premium}
                  solvedLabels={solvedLabels("en")}
                  headingOffset={2}
                  assetUrl={assetUrl}
                />
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
