import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { chooseReadingLanguage } from "@/app/actions/learn";
import { KeepPlace } from "@/components/keep-place";
import { LectureView } from "@/components/lecture-view";
import { LessonBlocks } from "@/components/lesson-blocks";
import { continuesInto, headingOnly as isHeadingOnly, headingTone } from "@/lib/book-heading";
import { typesetEquations } from "@/lib/typeset";
import { placeSignature, type PlaceBlock } from "@/lib/variant-place";
import { Notice, SkeletonLines } from "@/components/ui";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { GRADE_LABEL } from "@/lib/format";
import { LANGUAGE_COOKIE, missingLanguageNote, preferredLanguage, READING_LANGUAGES, subjectKey } from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Lesson" };

// BOOK-HEADING-01: a heading's colour by its depth (lib/book-heading.ts `headingTone`).
const TONE = { main: "text-accent", topic: "", sub: "text-subheading" } as const;

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
  chapter_start?: boolean;
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
  // BOOK-HEADING-01: where the book prints only this topic's heading and runs straight into its first subtopic
  // (Chemistry XI 14.4 into 14.4.1), the page goes on with that subtopic under its own heading instead of staying empty.
  const headingOnly = isHeadingOnly(reading);
  let cont: TopicReading | null = null;
  if (headingOnly && reading.next_topic_id) {
    const next = await api<TopicReading>(`/v1/topics/${reading.next_topic_id}/lesson${language === "en" ? "" : `?language=${language}`}`, token ? { token } : {});
    if (next.ok && continuesInto(reading, next.data)) cont = next.data;
  }
  const shown = cont ?? reading; // the topic whose lesson is on the page
  const lesson = shown.lesson;
  const grade = GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`;
  // CHAPTER-OPENING-01: owner-approved for every book after Chemistry (2026-10-27).
  const chapterOpening = reading.chapter_start === true;
  const empty = headingOnly && !cont; // a heading with nothing to go on with is not a lesson yet
  const readable = Boolean(lesson?.body) && !empty && !lesson?.locked && reading.availability !== "unavailable";
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
          <KeepPlace lessonId={lesson?.id ?? ""} signatures={(lesson?.body?.blocks ?? []).map((b) => placeSignature(b as PlaceBlock))} />
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
      {chapterOpening ? (
        // CHAPTER-OPENING-01 (owner trial, 2026-10-27): a chapter's introduction opens with the chapter itself: its name
        // large in the subject colour on a tinted panel, then the introduction's own title.
        <header className="space-y-5">
          <div className="relative overflow-hidden rounded-2xl border border-border bg-accent-soft px-6 py-7 sm:px-9 sm:py-10">
            <span aria-hidden className="pointer-events-none absolute -bottom-6 right-4 select-none text-[8rem] font-bold leading-none text-accent opacity-10 sm:text-[10rem]">
              {reading.chapter_number}
            </span>
            <div className="relative space-y-3">
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-accent">
                <Link href={`/learn/chapter/${reading.chapter_id}`} className="underline underline-offset-2">
                  {grade} · {reading.subject_name}
                </Link>
                {reading.availability === "private_preview" && (
                  <span className="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted" title="Not yet reviewed or published">
                    Draft preview
                  </span>
                )}
              </p>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Chapter {reading.chapter_number}</p>
              <p className="text-4xl font-bold tracking-tight text-accent sm:text-5xl">{reading.chapter_title}</p>
              <div aria-hidden className="h-1 w-16 rounded-full bg-accent" />
            </div>
          </div>
          {/* The page's heading stays the topic; the chapter above is its setting. */}
          <h1 className={`text-2xl font-semibold tracking-tight ${TONE[headingTone(reading.number) ?? "topic"]}`}>
            {reading.number ? `${reading.number} ${reading.title}` : reading.title}
          </h1>
        </header>
      ) : (
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
          <h1 className={`text-3xl font-semibold tracking-tight ${TONE[headingTone(reading.number) ?? "topic"]}`}>{reading.number ? `${reading.number} ${reading.title}` : reading.title}</h1>
          <p className="text-sm text-muted">{reading.chapter_title}</p>
        </header>
      )}
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
      {view === "lecture" && readable ? null : reading.availability === "unavailable" || !lesson?.body || empty ? (
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
          {cont && <h2 className="text-2xl font-semibold tracking-tight">{`${cont.number} ${cont.title}`}</h2>}
          <LessonBlocks
            blocks={lesson.body.blocks}
            typeset={typesetEquations(lesson.body.blocks)}
            blockIds
            dataSaver={dataSaver}
            runnable={lesson.language === "roman_ur"}
            assetUrl={(versionId) =>
              lesson.private_preview
                ? `/learn/topics/${shown.topic_id}/preview-assets/${versionId}`
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
        {shown.next_topic_id && (
          <Link href={`/learn/topic/${shown.next_topic_id}`} className="font-medium text-accent">
            Next topic →
          </Link>
        )}
      </nav>
    </article>
  );
}
