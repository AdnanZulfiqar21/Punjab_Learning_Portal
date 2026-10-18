import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { chooseReadingLanguage } from "@/app/actions/learn";
import { KeepPlace } from "@/components/keep-place";
import { LectureView } from "@/components/lecture-view";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Notice, SkeletonLines } from "@/components/ui";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { GRADE_LABEL } from "@/lib/format";
import { LANGUAGE_COOKIE, missingLanguageNote, preferredLanguage, READING_LANGUAGES, subjectKey } from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";

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

/**
 * A topic's lesson (pilot): "English | Roman Urdu" at the top, a compact header, then the lesson. The language choice
 * is kept on this device and in a signed-in learner's profile. Both variants share one block structure (ids b0, b1,
 * …), so switching returns to the same place.
 */
type TopicLecture = {
  availability: "available" | "coming";
  lectures: {
    id: string;
    title: string;
    language: string;
    duration_s: number;
    locked: boolean;
    stream_path: string | null;
    markers: { scene_id: string; label: string; start_s: number }[];
    transcript: { scene_id: string; text: string }[];
  }[];
};

export default function TopicPage({ params, searchParams }: PageProps<"/learn/topic/[topicId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading lesson" />}>
      {Promise.all([params, searchParams]).then(([{ topicId }, sp]) => <TopicView id={topicId} view={sp.view === "lecture" ? "lecture" : "read"} />)}
    </Suspense>
  );
}

async function TopicView({ id, view }: { id: string; view: "read" | "lecture" }) {
  if (!UUID.test(id)) notFound();
  const user = await currentUser();
  const token = user?.token;
  const jar = await cookies();
  const language = preferredLanguage(jar.get(LANGUAGE_COOKIE)?.value, user?.me.profile?.explanation_language);
  const res = await api<TopicReading>(`/v1/topics/${id}/lesson${language === "en" ? "" : `?language=${language}`}`, token ? { token } : {});
  if (!res.ok) notFound();
  const reading = res.data;
  const lesson = reading.lesson;
  const grade = GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`;
  const readable = Boolean(lesson?.body) && !lesson?.locked && reading.availability !== "unavailable";
  const note = lesson && readable ? missingLanguageNote(language, lesson.language) : null;
  const display = parseDisplay(jar.get(DISPLAY_COOKIE)?.value);
  const dataSaver = display ? display.dataSaver : (await headers()).get("save-data") === "on";
  const lectureRes = readable ? await api<TopicLecture>(`/v1/topics/${id}/lecture`, token ? { token } : {}) : null;
  const lecture = lectureRes?.ok ? lectureRes.data : null;
  const segment = "rounded-md px-4 py-1.5 text-sm";
  const on = `${segment} bg-surface font-semibold shadow-sm`;
  const off = `${segment} text-muted hover:text-foreground`;
  return (
    <article className="mx-auto max-w-3xl space-y-6" data-subject={subjectKey(reading.subject_name)}>
      {readable && (
        <form action={chooseReadingLanguage} className="sticky top-0 z-10 -mx-4 space-y-2 bg-background/95 px-4 py-2 backdrop-blur" aria-label="Explanation language">
          <input type="hidden" name="topic" value={reading.topic_id} />
          <KeepPlace lessonId={lesson?.id ?? ""} />
          <div role="group" aria-label="Read or watch" className="inline-flex rounded-lg border border-border bg-surface-muted p-0.5">
            {READING_LANGUAGES.map(([code, label]) =>
              view === "lecture" ? (
                <Link key={code} href={`/learn/topic/${reading.topic_id}`} aria-current={undefined} className={off}>
                  {label}
                </Link>
              ) : (
                <button key={code} type="submit" name="language" value={code} aria-pressed={code === language} className={code === language ? on : off}>
                  {label}
                </button>
              ),
            )}
            <Link href={`/learn/topic/${reading.topic_id}?view=lecture`} aria-current={view === "lecture" ? "page" : undefined} className={view === "lecture" ? on : off}>
              Lecture
            </Link>
          </div>
          {note && view !== "lecture" && (
            <p className="text-sm text-muted" role="status">
              {note}
            </p>
          )}
        </form>
      )}
      <header className="space-y-2">
        <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-accent">
          <Link href={`/learn/chapter/${reading.chapter_id}`} className="underline underline-offset-2">
            {grade} · {reading.subject_name} · Chapter {reading.chapter_number}
          </Link>
          {reading.availability === "private_preview" && (
            <span className="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted" title="Not yet reviewed or published">
              Draft preview
            </span>
          )}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">{reading.number ? `${reading.number} ${reading.title}` : reading.title}</h1>
        <p className="text-sm text-muted">{reading.chapter_title}</p>
      </header>
      {view === "lecture" && readable && (
        <section aria-label="Lecture" className="space-y-3">
          {lecture?.availability === "available" && lecture.lectures.length > 0 ? (
            lecture.lectures.some((l) => l.locked || !l.stream_path) ? (
              <Notice title="Included with a plan or the free 30-day trial">
                <Link href="/account" className="underline underline-offset-2">
                  Start your free trial or sign in
                </Link>{" "}
                to watch this lecture.
              </Notice>
            ) : (
              <LectureView
                parts={lecture.lectures.map((l) => ({
                  id: l.id,
                  title: l.title,
                  duration_s: l.duration_s,
                  src: `/learn/lectures/${l.id}/stream`,
                  markers: l.markers,
                  transcript: l.transcript,
                }))}
              />
            )
          ) : (
            <Notice title="The lecture for this topic is coming">
              Lectures are added topic by topic after an independent academic review. The lesson text below is complete.
            </Notice>
          )}
        </section>
      )}
      {view === "lecture" && readable ? null : reading.availability === "unavailable" || !lesson?.body ? (
        <Notice title="This topic’s lesson isn’t ready yet">The chapter outline lists the topic, but its lesson has not been published.</Notice>
      ) : lesson.locked ? (
        <Notice title="Included with a plan or the free 30-day trial">
          <Link href="/account" className="underline underline-offset-2">
            Start your free trial or sign in
          </Link>{" "}
          to read it.
        </Notice>
      ) : (
        <div className="space-y-4 text-[1.0625rem] leading-7 sm:text-[1.125rem] sm:leading-8" lang={lesson.language === "ur" ? "ur" : "en"} dir={lesson.language === "ur" ? "rtl" : undefined}>
          <LessonBlocks
            blocks={lesson.body.blocks}
            blockIds
            dataSaver={dataSaver}
            assetUrl={(versionId) =>
              lesson.private_preview
                ? `/learn/topics/${reading.topic_id}/preview-assets/${versionId}`
                : `/learn/lessons/${lesson.id}/assets/${versionId}`
            }
          />
        </div>
      )}
      <nav className="flex justify-between gap-3 border-t border-border pt-4 text-sm" aria-label="Topic navigation">
        {reading.previous_topic_id ? (
          <Link href={`/learn/topic/${reading.previous_topic_id}`} className="font-medium text-accent">
            ← Previous topic
          </Link>
        ) : (
          <span />
        )}
        {reading.next_topic_id && (
          <Link href={`/learn/topic/${reading.next_topic_id}`} className="font-medium text-accent">
            Next topic →
          </Link>
        )}
      </nav>
    </article>
  );
}
