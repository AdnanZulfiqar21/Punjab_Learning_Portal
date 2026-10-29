import type { Metadata } from "next";
import Link from "next/link";
import { cookies, headers } from "next/headers";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { FavouriteTopic, Lesson, ReadingPosition, StudyNote, TopicNode } from "@portal/contracts";
import { setLessonCompleted } from "@/app/actions/lessons";
import { LessonBlocks } from "@/components/lesson-blocks";
import { typesetEquations } from "@/lib/typeset";
import { LessonStartBeacon } from "@/components/lesson-start-beacon";
import { ReadingTracker } from "@/components/reading-tracker";
import { FavouriteButton, LessonNote, SaveFormulaButton } from "@/components/study-tools";
import { getChapter, getLessons } from "@/lib/api";
import { DISPLAY_COOKIE, parseDisplay } from "@/lib/display";
import { practiceOnly } from "@/lib/exercises";
import { CONTENT_STATE_TEXT, GRADE_LABEL, assessmentSummary, pageRange } from "@/lib/format";
import { LANGUAGE_NAME, subjectKey } from "@/lib/learn-context";
import { ButtonLink, buttonClasses } from "@/components/button";
import { Icon, SubjectIcon } from "@/components/icons";
import { StatChip } from "@/components/stat-chip";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser, deviceScope, features, sessionToken } from "@/lib/session";
import { TIME_ZONE } from "@/lib/dates";

export const metadata: Metadata = { title: "Chapter" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const LANGUAGES: [string, string][] = [
  ["en", "English"],
  ["ur", "اردو"],
  ["roman_ur", "Roman Urdu"],
];

/** A chapter (pilot): a compact header, the topics first, then the chapter's published lessons and textbook details. */
export default function ChapterPage({ params, searchParams }: PageProps<"/learn/chapter/[chapterId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading chapter" />}>
      {Promise.all([params, searchParams]).then(([{ chapterId }, sp]) => (
        <ChapterView id={chapterId} lang={typeof sp.lang === "string" && LANGUAGES.some(([k]) => k === sp.lang) ? sp.lang : "en"} />
      ))}
    </Suspense>
  );
}

async function ChapterView({ id, lang }: { id: string; lang: string }) {
  if (!UUID.test(id)) notFound();
  const res = await getChapter(id);
  if (!res.ok) notFound();
  const ch = res.data;
  const bc = ch.breadcrumb;
  // BOOK-EXERCISES-01: the end-of-chapter exercise (and BOOK-PAPERS-01 the Board papers) is solved in Practice, so
  // Learn lists only the book's topics.
  const topics = ch.topics.filter((t) => !practiceOnly(t.kind));
  const exerciseTopics = new Set(ch.topics.filter((t) => practiceOnly(t.kind)).map((t) => t.id));
  const gradeLabel = GRADE_LABEL[bc.grade.number];
  const state = CONTENT_STATE_TEXT[ch.content_state] ?? { label: ch.content_state, detail: "" };
  const exercises = assessmentSummary(ch.assessment_counts);
  return (
    <article className="space-y-8" data-subject={subjectKey(bc.subject.code)}>
      <div>
        <Breadcrumbs
          items={[
            { href: "/learn", label: "Learn" },
            { href: `/learn/${bc.grade.number}/${bc.subject.code}`, label: `${gradeLabel} ${bc.subject.name}` },
            { label: `${bc.chapter_label} ${ch.number}` },
          ]}
        />
        {/* DESIGN-01: the chapter opens on a glass hero in the subject colour, like its book (BOOK-PAGE-01). Only
            figures the API gives are shown. */}
        <header className="glass relative overflow-hidden rounded-card px-6 py-8 sm:px-9 sm:py-10">
          <span aria-hidden className="pointer-events-none absolute inset-0 bg-accent-soft opacity-60" />
          <span
            aria-hidden
            className="pointer-events-none absolute -bottom-8 right-4 select-none font-display text-[8rem] leading-none font-bold text-accent opacity-10 sm:text-[10rem]"
          >
            {ch.number}
          </span>
          <div className="relative space-y-4">
            <p className="flex items-center gap-3 text-sm font-semibold text-accent">
              <SubjectIcon subject={bc.subject.code} size={40} />
              <span>
                {gradeLabel} · {bc.subject.name} · {bc.chapter_label} {ch.number}
                {ch.contents_number != null && ch.contents_number !== ch.number && ` (Contents page: ${ch.contents_number})`}
              </span>
            </p>
            <h1 className="font-display text-[30px] leading-9 font-bold tracking-tight sm:text-[42px] sm:leading-[3.25rem]">{ch.title}</h1>
            <div aria-hidden className="h-1 w-16 rounded-full bg-accent" />
            {ch.main_concept && <p className="max-w-3xl text-muted sm:text-lg">{ch.main_concept}</p>}
            <ul className="flex flex-wrap gap-2 pt-1">
              <li>
                <StatChip icon="file-text">Pages {pageRange(ch.source.printed_start, ch.source.printed_end)}</StatChip>
              </li>
              {ch.visual_count > 0 && (
                <li>
                  <StatChip icon="image">{ch.visual_count} figures and tables</StatChip>
                </li>
              )}
            </ul>
          </div>
        </header>
      </div>

      {ch.status !== "complete" && (
        <Notice tone="warn" title={`This chapter is ${ch.status} in the supplied textbook file`}>
          Some pages are missing from the source. Topics from missing pages are not listed.
        </Notice>
      )}

      <section aria-labelledby="topics-heading" className="space-y-3">
        <h2 id="topics-heading" className="font-display text-2xl font-semibold tracking-tight">
          Topics
        </h2>
        {topics.length === 0 ? (
          <p className="text-muted">No topics are recorded for this chapter.</p>
        ) : (
          <Suspense fallback={<TopicList topics={topics} favourites={null} />}>
            <Topics topics={topics} />
          </Suspense>
        )}
      </section>

      <Notice title={state.label}>{state.detail}</Notice>

      <Suspense fallback={<SkeletonLines lines={3} label="Loading lessons" />}>
        <Lessons chapterId={ch.id} topics={topics} hidden={exerciseTopics} lang={lang} />
      </Suspense>

      <section aria-labelledby="source-heading" className="glass space-y-3 rounded-card p-[22px] text-sm">
        <h2 id="source-heading" className="flex items-center gap-2 font-display text-lg font-semibold">
          <Icon name="book-open" size={18} className="text-accent" />
          In your textbook
        </h2>
        <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[max-content_1fr]">
          <dt className="text-muted">Book pages</dt>
          <dd>{pageRange(ch.source.printed_start, ch.source.printed_end)}</dd>
          <dt className="text-muted">Figures and tables</dt>
          <dd>{ch.visual_count}</dd>
          {exercises.length > 0 && (
            <>
              <dt className="text-muted">End-of-chapter exercise</dt>
              <dd>{exercises.join(" · ")}</dd>
            </>
          )}
        </dl>
      </section>

      <nav aria-label="Chapter navigation" className="flex flex-wrap justify-between gap-3">
        {ch.previous_chapter_id ? (
          <ButtonLink href={`/learn/chapter/${ch.previous_chapter_id}`} variant="secondary">
            <Icon name="arrow-right" size={18} className="rotate-180" />
            Previous {bc.chapter_label.toLowerCase()}
          </ButtonLink>
        ) : (
          <span />
        )}
        {ch.next_chapter_id && (
          <ButtonLink href={`/learn/chapter/${ch.next_chapter_id}`} variant="secondary">
            Next {bc.chapter_label.toLowerCase()}
            <Icon name="arrow-right" size={18} />
          </ButtonLink>
        )}
      </nav>
    </article>
  );
}

function topicTitles(nodes: TopicNode[], out = new Map<string, string>()): Map<string, string> {
  for (const n of nodes) {
    out.set(n.id, n.number ? `${n.number} ${n.title}` : n.title);
    topicTitles(n.children, out);
  }
  return out;
}

const megabytes = (n: number) => (n < 100_000 ? `${Math.max(1, Math.round(n / 1000))} KB` : `${(n / 1_000_000).toFixed(1)} MB`);
const published = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE });

/** The chapter's published, independently reviewed lessons (P07), read in place; drafts never appear here. */
async function Lessons({ chapterId, topics, hidden, lang }: { chapterId: string; topics: TopicNode[]; hidden: Set<string>; lang: string }) {
  const res = await getLessons(chapterId, lang);
  // BOOK-EXERCISES-01: an exercise's lesson is read in Practice, never in the chapter's run of lessons.
  const lessons: Lesson[] = res.ok ? res.data.filter((l) => !l.topic_id || !hidden.has(l.topic_id)) : [];
  const token = await sessionToken();
  const doneRes = token && lessons.some((l) => !l.locked) ? await api<string[]>(`/v1/me/chapters/${encodeURIComponent(chapterId)}/completed-lessons`, { token }) : null;
  const done = new Set(doneRes?.ok ? doneRes.data : []);
  // LESSON-PROGRESS-01: the newest place this learner reached in the chapter, from any device.
  const placeRes = token && lessons.some((l) => !l.locked)
    ? await api<ReadingPosition | null>(`/v1/me/chapters/${encodeURIComponent(chapterId)}/reading-position`, { token })
    : null;
  const place = placeRes?.ok && placeRes.data && lessons.some((l) => l.id === placeRes.data!.lesson_id) ? placeRes.data : null;
  // STUDY-TOOLS-01: each readable lesson's private note (with its revision, so edits from stale copies are caught).
  const study = token ? (await features(token)).study_tools === true : false; // ROLLOUT-01
  const readable = token && study ? lessons.filter((l) => !l.locked && l.body) : [];
  const noteRes = await Promise.all(readable.map((l) => api<StudyNote>(`/v1/me/lessons/${encodeURIComponent(l.id)}/note`, { token })));
  const notes = new Map(readable.flatMap((l, i) => (noteRes[i].ok ? [[l.id, noteRes[i].data] as const] : [])));
  const user = notes.size > 0 ? await currentUser() : null; // ISOLATION-01: unsent drafts are kept per account
  const titles = topicTitles(topics);
  // SETTINGS-01: this device's data saver, or the browser's Save-Data hint when the device hasn't chosen.
  const display = parseDisplay((await cookies()).get(DISPLAY_COOKIE)?.value);
  const dataSaver = display ? display.dataSaver : (await headers()).get("save-data") === "on";
  return (
    <section aria-labelledby="lessons-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="lessons-heading" className="font-display text-2xl font-semibold tracking-tight">
          Lessons
        </h2>
        {lessons.length > 0 && (
          <nav aria-label="Lesson language" className="glass inline-flex gap-1 rounded-full p-1 text-sm">
            {LANGUAGES.map(([k, label]) => (
              <Link
                key={k}
                href={`/learn/chapter/${chapterId}${k === "en" ? "" : `?lang=${k}`}`}
                aria-current={k === lang ? "true" : undefined}
                lang={k === "ur" ? "ur" : "en"}
                className={`inline-flex min-h-11 items-center rounded-full px-4 transition duration-200 ${k === lang ? "bg-foreground font-semibold text-background shadow-glass" : "text-muted hover:bg-surface-muted hover:text-foreground"}`}
              >
                {label}
              </Link>
            ))}
          </nav>
        )}
      </div>
      {place && place.lesson_id !== lessons[0]?.id && (
        <p className="glass flex items-center gap-2 rounded-inner px-4 py-3 text-sm">
          <Icon name="play" size={16} className="shrink-0 text-accent" />
          <a href={`#lesson-${place.lesson_id}`} className="font-medium text-accent underline underline-offset-2">
            Continue where you left off: {place.lesson_title}
          </a>
        </p>
      )}
      {token && <ReadingTracker lessonIds={lessons.filter((l) => !l.locked && l.body).map((l) => l.id)} />}
      {lessons.length === 0 ? (
        <p className="text-muted">
          No reviewed lessons are published for this chapter yet. Lessons appear here only after an independent subject
          reviewer approves them. Until then, use the topic outline and your textbook pages.
        </p>
      ) : (
        lessons.map((l, i) => (
          <article key={l.id} aria-labelledby={`lesson-${l.id}`} className="space-y-4 rounded-card border border-border bg-surface p-5 shadow-glass sm:p-7">
            {l.requested_language_missing && (
              <p className="rounded-lg bg-surface-muted px-3 py-2 text-sm">
                This lesson isn&apos;t available in {LANGUAGE_NAME[lang]} yet, so it&apos;s shown in {LANGUAGE_NAME[l.language]}.
              </p>
            )}
            <header className="space-y-1" lang={l.language === "ur" ? "ur" : "en"} dir={l.language === "ur" ? "rtl" : undefined}>
              <h3 id={`lesson-${l.id}`} className="font-display text-2xl font-semibold tracking-tight">
                {l.title}
              </h3>
              <p className="text-sm text-muted">
                {l.topic_id && titles.get(l.topic_id) ? `${titles.get(l.topic_id)} · ` : ""}
                {l.access_tier === "preview" ? "Free preview · " : ""}Reviewed lesson · version {l.version} ·
                published {published(l.published_at)}
              </p>
              {/* P07.S3.T3 (LESSON-SIZE-01): what the lesson's images and handouts cost to download, before they load. */}
              {!l.locked && (l.download_bytes ?? 0) > 0 && (
                <p className="text-sm text-muted">
                  Images and handouts: {megabytes(l.download_bytes!)}
                  {dataSaver ? " · data saver is on, so each loads only when you tap it" : ""}
                </p>
              )}
            </header>
            {l.locked || !l.body ? (
              <div className="rounded-inner bg-surface-muted p-4 text-sm">
                <p className="font-medium">This lesson is included with a plan or the free 30-day trial.</p>
                <p className="text-muted">
                  <Link href="/account" className="text-accent underline underline-offset-2">
                    Start your free trial or sign in
                  </Link>{" "}
                  to read it.
                </p>
              </div>
            ) : (
              <div lang={l.language === "ur" ? "ur" : "en"} dir={l.language === "ur" ? "rtl" : undefined}>
                {token && <LessonStartBeacon lessonId={l.id} language={l.language} />}
                <LessonBlocks
                  blocks={l.body.blocks as { type: string }[]}
                  typeset={typesetEquations(l.body.blocks as { type: string }[])}
                  headingOffset={2}
                  assetUrl={(v) => `/learn/lessons/${l.id}/assets/${v}`}
                  dataSaver={dataSaver}
                  equationAction={token && study ? (i) => <SaveFormulaButton lessonId={l.id} index={i} /> : undefined}
                />
              </div>
            )}
            {token && !l.locked && l.body && (
              <form action={setLessonCompleted.bind(null, l.id, chapterId, !done.has(l.id))} className="flex flex-wrap items-center gap-3">
                <button type="submit" className={buttonClasses({ variant: "secondary" })}>
                  {done.has(l.id) ? "✓ Completed: undo" : "Mark as completed"}
                </button>
                <span className="text-xs text-muted">Completion tracks your reading only. It isn&apos;t evidence of what you know.</span>
              </form>
            )}
            {notes.has(l.id) && user && <LessonNote lessonId={l.id} scope={deviceScope(user.me.id)} initial={notes.get(l.id)!} />}
            {i + 1 < lessons.length && (
              // P11.S2.T1: one lesson leads to the next, in the reviewed order of the chapter.
              <p className="border-t border-border pt-3 text-sm">
                <a href={`#lesson-${lessons[i + 1].id}`} className="font-medium text-accent underline underline-offset-2">
                  Next lesson: {lessons[i + 1].title}
                </a>
              </p>
            )}
          </article>
        ))
      )}
    </section>
  );
}

/** Topic outline with favourite stars for a signed-in learner (STUDY-TOOLS-01). The outline itself stays public. */
async function Topics({ topics }: { topics: TopicNode[] }) {
  const token = await sessionToken();
  const res = token ? await api<FavouriteTopic[]>("/v1/me/favourites", { token }) : null;
  return <TopicList topics={topics} favourites={res?.ok ? new Set(res.data.map((f) => f.topic_id)) : null} />;
}

function TopicList({ topics, favourites }: { topics: TopicNode[]; favourites: Set<string> | null }) {
  return (
    <ol className="glass divide-y divide-border overflow-hidden rounded-card">
      {topics.map((t) => (
        <TopicItem key={t.id} topic={t} favourites={favourites} />
      ))}
    </ol>
  );
}

/** Each topic opens its own lesson page. Subtopics are always listed under their topic, indented, as the book's
 * contents show them (owner, 2026-10-28: "baki ka sb topics ... kaha hain"); only bullet points fold under "Outline".
 * The contents stay plain: every number in the text colour (owner, 2026-10-28). */
function TopicItem({ topic, favourites, depth = 0 }: { topic: TopicNode; favourites: Set<string> | null; depth?: number }) {
  const star = favourites && (
    <FavouriteButton topicId={topic.id} label={topic.number ? `${topic.number} ${topic.title}` : topic.title} initial={favourites.has(topic.id)} />
  );
  return (
    <li className={depth ? "py-0.5" : "px-4 py-2 sm:px-5"}>
      <div className="flex items-center gap-2">
        <Link href={`/learn/topic/${topic.id}`} className="flex min-w-0 flex-1 items-baseline gap-3 py-1.5 hover:text-accent">
          {topic.number && (
            <span className={`shrink-0 text-sm font-semibold text-foreground ${depth ? "w-14 sm:w-16" : "w-12"}`}>
              {topic.number}
              {/* BOOK-NUMBER-01: where the book misprints the number, its own number to find the page. */}
              {topic.book_number && <span className="block text-xs font-normal whitespace-nowrap text-muted">Book# {topic.book_number}</span>}
            </span>
          )}
          <span className={depth ? "" : "font-medium"}>{topic.title}</span>
        </Link>
        {star}
      </div>
      {topic.points.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer list-none py-1 pl-15 text-muted hover:text-foreground">Outline</summary>
          <ul className="mt-1 ml-15 list-disc space-y-1 pl-5 text-muted">
            {topic.points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </details>
      )}
      {topic.children.length > 0 && (
        <ol className="mt-1 ml-3 border-l-2 border-border pl-2 sm:ml-15 sm:pl-3">
          {topic.children.map((c) => (
            <TopicItem key={c.id} topic={c} favourites={favourites} depth={depth + 1} />
          ))}
        </ol>
      )}
    </li>
  );
}
