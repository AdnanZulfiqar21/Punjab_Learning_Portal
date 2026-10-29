import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import { chooseReadingLanguage } from "@/app/actions/learn";
import { KeepPlace } from "@/components/keep-place";
import { LectureView } from "@/components/lecture-view";
import { LessonBlocks } from "@/components/lesson-blocks";
import { continuesInto, headingOnly as isHeadingOnly, headingTone } from "@/lib/book-heading";
import { premiumBook } from "@/lib/book-style";
import { typesetEquations } from "@/lib/typeset";
import { placeSignature, type PlaceBlock } from "@/lib/variant-place";
import { ButtonLink } from "@/components/button";
import { Icon } from "@/components/icons";
import { Notice, SkeletonLines } from "@/components/ui";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { practiceOnly } from "@/lib/exercises";
import { GRADE_LABEL } from "@/lib/format";
import { LANGUAGE_COOKIE, missingLanguageNote, preferredLanguage, READING_LANGUAGES, subjectKey } from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Lesson" };

// BOOK-HEADING-01: a heading's colour by its depth (lib/book-heading.ts `headingTone`).
// DESIGN-01: the page's chrome (switch, header, chapter opening, navigation) is glass; the lesson stays on a solid card.
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
  kind?: "topic" | "exercise" | "paper";
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
  // BOOK-EXERCISES-01: the end-of-chapter exercise (and BOOK-PAPERS-01 a Board paper) is solved in Practice; an old
  // link or a search hit goes there.
  if (practiceOnly(reading.kind)) redirect(`/practice/exercises/${reading.topic_id}`);
  // BOOK-HEADING-01: where the book prints only this topic's heading and runs straight into its first subtopic
  // (Chemistry 11 14.4 into 14.4.1), the page goes on with that subtopic under its own heading instead of staying empty.
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
  // DESIGN-01: a pill segmented control; the chosen segment is the dark primary pill.
  const segment = "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-full px-4 text-sm transition duration-200 sm:px-5";
  const on = `${segment} bg-foreground font-semibold text-background shadow-glass`;
  const off = `${segment} font-medium text-muted hover:bg-surface-muted hover:text-foreground`;
  const draft = (
    <span
      className="inline-flex items-center rounded-full border border-warn/30 bg-warn-soft px-2.5 py-0.5 text-xs font-semibold text-foreground"
      title="Not yet reviewed or published"
    >
      Draft preview
    </span>
  );
  return (
    <article className="mx-auto max-w-3xl space-y-6" data-subject={subjectKey(reading.subject_name)}>
      {readable && (
        <form data-reading-bar action={chooseReadingLanguage} className="sticky top-0 z-10 -mx-4 space-y-2 bg-background/90 px-4 py-2.5 backdrop-blur" aria-label="Explanation language">
          <input type="hidden" name="topic" value={reading.topic_id} />
          <KeepPlace lessonId={lesson?.id ?? ""} signatures={(lesson?.body?.blocks ?? []).map((b) => placeSignature(b as PlaceBlock))} />
          <div role="group" aria-label="Read or watch" className="glass inline-flex max-w-full gap-1 rounded-full p-1">
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
              <Icon name="play" size={14} />
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
          <div className="glass relative overflow-hidden rounded-card px-6 py-8 sm:px-9 sm:py-11">
            <span aria-hidden className="pointer-events-none absolute inset-0 bg-accent-soft opacity-80" />
            <span aria-hidden className="pointer-events-none absolute -bottom-6 right-4 select-none font-display text-[8rem] font-bold leading-none text-accent opacity-10 sm:text-[10rem]">
              {reading.chapter_number}
            </span>
            <div className="relative space-y-3">
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-accent">
                <Link href={`/learn/chapter/${reading.chapter_id}`} className="underline underline-offset-2">
                  {grade} · {reading.subject_name}
                </Link>
                {reading.availability === "private_preview" && draft}
              </p>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Chapter {reading.chapter_number}</p>
              <p className="font-display text-4xl font-bold tracking-tight text-accent sm:text-5xl">{reading.chapter_title}</p>
              <div aria-hidden className="h-1 w-16 rounded-full bg-accent" />
            </div>
          </div>
          {/* The page's heading stays the topic; the chapter above is its setting. */}
          <h1 className={`font-display text-[26px] leading-8 font-semibold tracking-tight sm:text-3xl ${TONE[headingTone(reading.number) ?? "topic"]}`}>
            {reading.number ? `${reading.number} ${reading.title}` : reading.title}
          </h1>
        </header>
      ) : (
        <header className="glass space-y-3 rounded-card px-6 py-6 sm:px-8 sm:py-7">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-accent">
            <Link href={`/learn/chapter/${reading.chapter_id}`} className="inline-flex items-center gap-1.5 underline underline-offset-2">
              <Icon name="book-open" size={16} />
              {grade} · {reading.subject_name} · Chapter {reading.chapter_number}
            </Link>
            {reading.availability === "private_preview" && draft}
          </p>
          <h1 className={`font-display text-[28px] leading-9 font-bold tracking-tight sm:text-[36px] sm:leading-[2.75rem] ${TONE[headingTone(reading.number) ?? "topic"]}`}>
            {reading.number ? `${reading.number} ${reading.title}` : reading.title}
          </h1>
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
        // Owner rule 5: the lesson is read on a solid surface, never on glass.
        <div className="space-y-4 rounded-card border border-border bg-surface px-4 py-5 text-[1.0625rem] leading-7 shadow-glass sm:px-8 sm:py-8 sm:text-[1.125rem] sm:leading-8" lang={lesson.language === "ur" ? "ur" : "en"} dir={lesson.language === "ur" ? "rtl" : undefined}>
          {cont && <h2 className="font-display text-2xl font-semibold tracking-tight">{`${cont.number} ${cont.title}`}</h2>}
          <LessonBlocks
            blocks={lesson.body.blocks}
            typeset={typesetEquations(lesson.body.blocks)}
            blockIds
            dataSaver={dataSaver}
            premium={premiumBook(subjectKey(reading.subject_name), reading.grade_number)}
            runnable={lesson.language === "roman_ur"}
            assetUrl={(versionId) =>
              lesson.private_preview
                ? `/learn/topics/${shown.topic_id}/preview-assets/${versionId}`
                : `/learn/lessons/${lesson.id}/assets/${versionId}`
            }
          />
        </div>
      )}
      <nav className="flex flex-wrap justify-between gap-3 pt-2" aria-label="Topic navigation">
        {reading.previous_topic_id ? (
          <ButtonLink href={`/learn/topic/${reading.previous_topic_id}`} variant="secondary">
            <Icon name="arrow-right" size={18} className="rotate-180" />
            Previous topic
          </ButtonLink>
        ) : (
          <span />
        )}
        {shown.next_topic_id && (
          <ButtonLink href={`/learn/topic/${shown.next_topic_id}`} variant="secondary" className="ml-auto">
            Next topic
            <Icon name="arrow-right" size={18} />
          </ButtonLink>
        )}
      </nav>
    </article>
  );
}
