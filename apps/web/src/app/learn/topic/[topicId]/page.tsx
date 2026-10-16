import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, sessionToken } from "@/lib/session";

export const metadata: Metadata = { title: "Lesson" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type TopicLesson = {
  id: string;
  title: string;
  language: string;
  private_preview: boolean;
  locked: boolean;
  status: string;
  body: { blocks: { type: string }[] } | null;
  requested_language_missing: boolean;
  available_languages: string[];
};

type TopicReading = {
  topic_id: string;
  number: string | null;
  title: string;
  chapter_id: string;
  chapter_number: number;
  chapter_title: string;
  grade_number: number;
  subject_name: string;
  availability: "published" | "private_preview" | "unavailable";
  lesson: TopicLesson | null;
  previous_topic_id: string | null;
  next_topic_id: string | null;
};

export default function TopicPage({ params }: PageProps<"/learn/topic/[topicId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading lesson" />}>
      {params.then(({ topicId }) => <TopicView id={topicId} />)}
    </Suspense>
  );
}

async function TopicView({ id }: { id: string }) {
  if (!UUID.test(id)) notFound();
  const token = await sessionToken();
  const res = await api<TopicReading>(`/v1/topics/${id}/lesson`, token ? { token } : {});
  if (!res.ok) notFound();
  const reading = res.data;
  const lesson = reading.lesson;
  const grade = GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`;
  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <p className="text-sm font-medium text-accent">
        <Link href={`/learn/chapter/${reading.chapter_id}`} className="underline underline-offset-2">
          {grade} · {reading.subject_name} · Chapter {reading.chapter_number}
        </Link>
      </p>
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">{reading.number ? `${reading.number} ${reading.title}` : reading.title}</h1>
        <p className="text-muted">{reading.chapter_title}</p>
      </header>
      {reading.availability === "private_preview" && (
        <Notice title="Private draft">This lesson is not published. Only staff who cover this subject can read it.</Notice>
      )}
      {reading.availability === "unavailable" || !lesson?.body ? (
        <p>This lesson is not ready yet. An outline is not the lesson.</p>
      ) : lesson.locked ? (
        <Notice title="Included with a plan or the free 30-day trial">
          <Link href="/account" className="underline underline-offset-2">
            Start your free trial or sign in
          </Link>{" "}
          to read it.
        </Notice>
      ) : (
        <div className="space-y-4 text-[1.125rem] leading-8">
          <LessonBlocks
            blocks={lesson.body.blocks}
            assetUrl={(versionId) =>
              lesson.private_preview
                ? `/learn/topics/${reading.topic_id}/preview-assets/${versionId}`
                : `/learn/lessons/${lesson.id}/assets/${versionId}`
            }
          />
        </div>
      )}
      <nav className="flex justify-between gap-3 text-sm" aria-label="Topic navigation">
        {reading.previous_topic_id ? (
          <Link href={`/learn/topic/${reading.previous_topic_id}`} className="font-medium text-accent">
            Previous topic
          </Link>
        ) : (
          <span />
        )}
        {reading.next_topic_id && (
          <Link href={`/learn/topic/${reading.next_topic_id}`} className="font-medium text-accent">
            Next topic
          </Link>
        )}
      </nav>
    </article>
  );
}
