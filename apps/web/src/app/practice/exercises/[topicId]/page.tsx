import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import { chooseReadingLanguage } from "@/app/actions/learn";
import { KeepPlace } from "@/components/keep-place";
import { LessonBlocks } from "@/components/lesson-blocks";
import { premiumBook } from "@/lib/book-style";
import { exerciseTitle, revealLabel } from "@/lib/exercises";
import { typesetEquations } from "@/lib/typeset";
import { placeSignature, type PlaceBlock } from "@/lib/variant-place";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { GRADE_LABEL } from "@/lib/format";
import { LANGUAGE_COOKIE, missingLanguageNote, preferredLanguage, READING_LANGUAGES, subjectKey } from "@/lib/learn-context";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Book exercise", robots: { index: false } };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type ExerciseReading = {
  topic_id: string;
  chapter_id: string;
  chapter_number: number;
  chapter_title: string;
  grade_number: number;
  subject_name: string;
  availability: "published" | "private_preview" | "unavailable";
  kind?: "topic" | "exercise";
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
 */
export default function ExercisePage({ params }: PageProps<"/practice/exercises/[topicId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading exercise" />}>
      {params.then(({ topicId }) => (
        <ExerciseView id={topicId} />
      ))}
    </Suspense>
  );
}

async function ExerciseView({ id }: { id: string }) {
  if (!UUID.test(id)) notFound();
  const user = await currentUser();
  const token = user?.token;
  const jar = await cookies();
  const language = preferredLanguage(jar.get(LANGUAGE_COOKIE)?.value, user?.me.profile?.explanation_language);
  const res = await api<ExerciseReading>(`/v1/topics/${id}/lesson${language === "en" ? "" : `?language=${language}`}`, token ? { token } : {});
  if (!res.ok) notFound();
  const reading = res.data;
  if (reading.kind !== "exercise") redirect(`/learn/topic/${reading.topic_id}`); // a book topic is read in Learn
  const lesson = reading.lesson;
  const grade = GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`;
  const subject = subjectKey(reading.subject_name);
  const readable = Boolean(lesson?.body) && !lesson?.locked && reading.availability !== "unavailable";
  const note = lesson && readable ? missingLanguageNote(language, lesson.language) : null;
  const display = parseDisplay(jar.get(DISPLAY_COOKIE)?.value);
  const dataSaver = display ? display.dataSaver : (await headers()).get("save-data") === "on";
  const back = `/practice/exercises?grade=${reading.grade_number}${subject ? `&subject=${subject}` : ""}`;
  const segment = "rounded-md px-4 py-1.5 text-sm";
  return (
    <article className="mx-auto max-w-3xl space-y-6" data-subject={subject}>
      <Breadcrumbs
        items={[
          { href: "/practice", label: "Practice" },
          { href: back, label: "Book exercises" },
          { label: exerciseTitle("Chapter", reading.chapter_number) },
        ]}
      />
      {readable && (
        <form action={chooseReadingLanguage} className="sticky top-0 z-10 -mx-4 space-y-2 bg-background/95 px-4 py-2 backdrop-blur" aria-label="Explanation language">
          <input type="hidden" name="topic" value={reading.topic_id} />
          <input type="hidden" name="place" value="exercise" />
          <KeepPlace lessonId={lesson?.id ?? ""} signatures={(lesson?.body?.blocks ?? []).map((b) => placeSignature(b as PlaceBlock))} />
          <div role="group" aria-label="Exercise language" className="inline-flex rounded-lg border border-border bg-surface-muted p-0.5">
            {READING_LANGUAGES.map(([code, label]) => (
              <button
                key={code}
                type="submit"
                name="language"
                value={code}
                aria-pressed={code === language}
                className={code === language ? `${segment} bg-surface font-semibold shadow-sm` : `${segment} text-muted hover:text-foreground`}
              >
                {label}
              </button>
            ))}
          </div>
          {note && (
            <p className="text-sm text-muted" role="status">
              {note}
            </p>
          )}
        </form>
      )}
      <header className="space-y-2">
        <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-accent">
          <span>
            {grade} · {reading.subject_name}
          </span>
          {reading.availability === "private_preview" && (
            <span className="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted" title="Not yet reviewed or published">
              Draft preview
            </span>
          )}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">{exerciseTitle("Chapter", reading.chapter_number)}</h1>
        <p className="text-sm text-muted">{reading.chapter_title}</p>
      </header>
      {reading.availability === "unavailable" || !lesson?.body ? (
        <Notice title="This exercise isn’t solved here yet">The chapter&apos;s exercise is in your textbook; its worked answers have not been published yet.</Notice>
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
            typeset={typesetEquations(lesson.body.blocks)}
            blockIds
            dataSaver={dataSaver}
            premium={premiumBook(subject, reading.grade_number)}
            runnable={lesson.language === "roman_ur"}
            revealLabel={revealLabel(lesson.language)}
            assetUrl={(versionId) =>
              lesson.private_preview ? `/learn/topics/${reading.topic_id}/preview-assets/${versionId}` : `/learn/lessons/${lesson.id}/assets/${versionId}`
            }
          />
        </div>
      )}
      <nav className="border-t border-border pt-4 text-sm" aria-label="Exercise navigation">
        <Link href={back} className="font-medium text-accent">
          ← All book exercises
        </Link>
      </nav>
    </article>
  );
}
