import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import { chooseReadingLanguage } from "@/app/actions/learn";
import { KeepPlace } from "@/components/keep-place";
import { LessonBlocks } from "@/components/lesson-blocks";
import { MathText } from "@/components/math-text";
import { premiumBook } from "@/lib/book-style";
import { practiceOnly, practiceTitle, revealLabel } from "@/lib/exercises";
import { solvedLabels } from "@/lib/solved-labels";
import { typesetEquations } from "@/lib/typeset";
import { placeSignature, type PlaceBlock } from "@/lib/variant-place";
import { Icon } from "@/components/icons";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { GRADE_LABEL } from "@/lib/format";
import { LANGUAGE_COOKIE, missingLanguageNote, preferredLanguage, READING_LANGUAGES, subjectKey } from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Book exercise", robots: { index: false } };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type ExerciseReading = {
  topic_id: string;
  title: string;
  chapter_id: string;
  chapter_number: number;
  chapter_title: string;
  grade_number: number;
  subject_name: string;
  availability: "published" | "private_preview" | "unavailable";
  kind?: "topic" | "exercise" | "paper";
  lesson: {
    id: string;
    language: string;
    private_preview: boolean;
    locked: boolean;
    body: { blocks: { type: string }[] } | null;
  } | null;
};

/**
 * BOOK-EXERCISES-01: a chapter's end-of-chapter exercise, solved. "English | Roman Urdu" only (no lecture), the same
 * lesson renderer and language choice as a topic, and the self-check answers revealed as "Show answer".
 * BOOK-PAPERS-01: a Board paper at the end of the book (paper pattern, model paper) opens here too, under its own title.
 * VIDEO-SOLUTION-01 (owner, 2026-11-05): a Mathematics exercise adds a third view, "Video Solution": every question
 * with its own video solution, or "Video not available yet" until its video is added. Worked examples never get one.
 */
export default function ExercisePage({ params, searchParams }: PageProps<"/practice/exercises/[topicId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading exercise" />}>
      {Promise.all([params, searchParams]).then(([{ topicId }, sp]) => (
        <ExerciseView id={topicId} video={sp.view === "video"} />
      ))}
    </Suspense>
  );
}

type QuestionBlock = { type: string; ref?: unknown; prompt?: unknown };

async function ExerciseView({ id, video: wantsVideo }: { id: string; video: boolean }) {
  if (!UUID.test(id)) notFound();
  const user = await currentUser();
  const token = user?.token;
  const jar = await cookies();
  const language = preferredLanguage(jar.get(LANGUAGE_COOKIE)?.value, user?.me.profile?.explanation_language);
  const res = await api<ExerciseReading>(`/v1/topics/${id}/lesson${language === "en" ? "" : `?language=${language}`}`, token ? { token } : {});
  if (!res.ok) notFound();
  const reading = res.data;
  if (!practiceOnly(reading.kind)) redirect(`/learn/topic/${reading.topic_id}`); // a book topic is read in Learn
  const paper = reading.kind === "paper";
  const title = practiceTitle(reading);
  const lesson = reading.lesson;
  const grade = GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`;
  const subject = subjectKey(reading.subject_name);
  const readable = Boolean(lesson?.body) && !lesson?.locked && reading.availability !== "unavailable";
  // VIDEO-SOLUTION-01: Mathematics exercises only (never a worked example, never another book's exercise).
  const videoTab = subject === "mathematics" && reading.kind === "exercise" && readable;
  const video = videoTab && wantsVideo;
  const questions = ((lesson?.body?.blocks ?? []) as QuestionBlock[]).filter((b) => b.type === "checkpoint");
  const note = lesson && readable ? missingLanguageNote(language, lesson.language) : null;
  const display = parseDisplay(jar.get(DISPLAY_COOKIE)?.value);
  const dataSaver = display ? display.dataSaver : (await headers()).get("save-data") === "on";
  const back = `/practice/exercises?grade=${reading.grade_number}${subject ? `&subject=${subject}` : ""}`;
  // DESIGN-01: the same pill switch as a topic; the chosen language is the dark primary pill.
  const segment = "inline-flex min-h-11 items-center justify-center rounded-full px-4 text-sm transition duration-200 sm:px-5";
  const on = `${segment} bg-foreground font-semibold text-background shadow-glass`;
  const off = `${segment} font-medium text-muted hover:bg-surface-muted hover:text-foreground`;
  return (
    <article className="mx-auto max-w-3xl space-y-6" data-subject={subject}>
      <Breadcrumbs
        items={[
          { href: "/practice", label: "Practice" },
          { href: back, label: "Book exercises" },
          { label: title },
        ]}
      />
      {readable && (
        <form data-reading-bar action={chooseReadingLanguage} className="sticky top-0 z-10 -mx-4 space-y-2 bg-background/90 px-4 py-2.5 backdrop-blur" aria-label="Explanation language">
          <input type="hidden" name="topic" value={reading.topic_id} />
          <input type="hidden" name="place" value="exercise" />
          <KeepPlace lessonId={lesson?.id ?? ""} signatures={(lesson?.body?.blocks ?? []).map((b) => placeSignature(b as PlaceBlock))} />
          <div role="group" aria-label={videoTab ? "Read or watch" : "Exercise language"} className="glass inline-flex max-w-full gap-1 rounded-full p-1">
            {READING_LANGUAGES.map(([code, label]) => (
              <button
                key={code}
                type="submit"
                name="language"
                value={code}
                aria-pressed={!video && code === language}
                className={!video && code === language ? on : off}
              >
                {label}
              </button>
            ))}
            {videoTab && (
              <Link href={`/practice/exercises/${reading.topic_id}?view=video`} aria-current={video ? "page" : undefined} className={`${video ? on : off} gap-1.5`}>
                <Icon name="play" size={14} />
                Video Solution
              </Link>
            )}
          </div>
          {note && !video && (
            <p className="text-sm text-muted" role="status">
              {note}
            </p>
          )}
        </form>
      )}
      <header className="glass space-y-3 rounded-card px-6 py-6 sm:px-8 sm:py-7">
        <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-accent">
          <span className="inline-flex items-center gap-1.5">
            <Icon name={paper ? "file-text" : "list-checks"} size={16} />
            {grade} · {reading.subject_name}
          </span>
          {reading.availability === "private_preview" && (
            <span
              className="inline-flex items-center rounded-full border border-warn/30 bg-warn-soft px-2.5 py-0.5 text-xs font-semibold text-foreground"
              title="Not yet reviewed or published"
            >
              Draft preview
            </span>
          )}
        </p>
        <h1 className="font-display text-[28px] leading-9 font-bold tracking-tight sm:text-[36px] sm:leading-[2.75rem]">{title}</h1>
        <p className="text-sm text-muted">{paper ? "Board model paper" : reading.chapter_title}</p>
      </header>
      {video ? (
        <section aria-labelledby="video-solutions" className="space-y-4">
          <h2 id="video-solutions" className="sr-only">
            Video solutions
          </h2>
          <Notice title="Video solutions are not available yet">
            Every question of this exercise will get its own video solution, explained step by step. Until a question&apos;s video is added, its
            worked solution is in the English and Roman Urdu views.
          </Notice>
          <ol className="space-y-3">
            {questions.map((q, i) => (
              <li key={i} className="rounded-card border border-border bg-surface px-4 py-4 shadow-sm" data-ref={typeof q.ref === "string" ? q.ref : undefined}>
                {typeof q.ref === "string" && <p className="text-xs font-semibold tracking-wide text-accent-strong uppercase">Question {q.ref}</p>}
                <p className="mt-1 whitespace-pre-wrap">
                  <MathText text={typeof q.prompt === "string" ? q.prompt : ""} />
                </p>
                <p className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1 text-sm font-medium text-muted" role="status">
                  <Icon name="play" size={14} />
                  Video not available yet
                </p>
              </li>
            ))}
          </ol>
        </section>
      ) : reading.availability === "unavailable" || !lesson?.body ? (
        paper ? (
          <Notice title="This paper isn’t solved here yet">The paper is at the end of your textbook; its worked answers have not been published yet.</Notice>
        ) : (
          <Notice title="This exercise isn’t solved here yet">The chapter&apos;s exercise is in your textbook; its worked answers have not been published yet.</Notice>
        )
      ) : lesson.locked ? (
        <Notice title="Included with a plan or the free 30-day trial">
          <Link href="/account" className="underline underline-offset-2">
            Start your free trial or sign in
          </Link>{" "}
          to read it.
        </Notice>
      ) : (
        // Owner rule 5: the worked exercise is read on a solid surface, never on glass.
        <div className="space-y-4 rounded-card border border-border bg-surface px-4 py-5 text-[1.0625rem] leading-7 shadow-glass sm:px-8 sm:py-8 sm:text-[1.125rem] sm:leading-8" lang={lesson.language === "ur" ? "ur" : "en"} dir={lesson.language === "ur" ? "rtl" : undefined}>
          <LessonBlocks
            blocks={lesson.body.blocks}
            typeset={typesetEquations(lesson.body.blocks)}
            blockIds
            dataSaver={dataSaver}
            premium={premiumBook(subject, reading.grade_number)}
            runnable={lesson.language === "roman_ur"}
            revealLabel={revealLabel(lesson.language)}
            solvedLabels={solvedLabels(lesson.language)}
            assetUrl={(versionId) =>
              lesson.private_preview ? `/learn/topics/${reading.topic_id}/preview-assets/${versionId}` : `/learn/lessons/${lesson.id}/assets/${versionId}`
            }
          />
        </div>
      )}
      <nav className="pt-2 text-sm" aria-label="Exercise navigation">
        <Link
          href={back}
          className="glass inline-flex min-h-11 items-center gap-2 rounded-full px-5 font-semibold text-foreground shadow-none transition duration-200 hover:border-accent hover:text-accent"
        >
          ← All book exercises
        </Link>
      </nav>
    </article>
  );
}
