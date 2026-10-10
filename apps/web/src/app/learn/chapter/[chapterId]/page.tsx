import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { Lesson, TopicNode } from "@portal/contracts";
import { setLessonCompleted } from "@/app/actions/lessons";
import { LessonBlocks } from "@/components/lesson-blocks";
import { LessonStartBeacon } from "@/components/lesson-start-beacon";
import { getChapter, getLessons } from "@/lib/api";
import { CONTENT_STATE_TEXT, GRADE_LABEL, assessmentSummary, pageRange } from "@/lib/format";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, sessionToken } from "@/lib/session";

export const metadata: Metadata = { title: "Chapter" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const LANGUAGES: [string, string][] = [
  ["en", "English"],
  ["ur", "اردو"],
  ["roman_ur", "Roman Urdu"],
];
const LANGUAGE_NAME: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };

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
  const gradeLabel = GRADE_LABEL[bc.grade.number];
  const state = CONTENT_STATE_TEXT[ch.content_state] ?? { label: ch.content_state, detail: "" };
  const exercises = assessmentSummary(ch.assessment_counts);
  return (
    <article className="space-y-8">
      <div>
        <Breadcrumbs
          items={[
            { href: "/learn", label: "Learn" },
            { href: `/learn/${bc.grade.number}/${bc.subject.code}`, label: `${gradeLabel} ${bc.subject.name}` },
            { label: `${bc.chapter_label} ${ch.number}` },
          ]}
        />
        <p className="text-sm font-medium text-accent">
          {gradeLabel} · {bc.subject.name} · {bc.chapter_label} {ch.number}
          {ch.contents_number != null && ch.contents_number !== ch.number && ` (Contents page: ${ch.contents_number})`}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{ch.title}</h1>
        {ch.main_concept && <p className="mt-3 max-w-3xl text-muted">{ch.main_concept}</p>}
      </div>

      <Notice title={state.label}>{state.detail}</Notice>
      {ch.status !== "complete" && (
        <Notice tone="warn" title={`This chapter is ${ch.status} in the supplied textbook file`}>
          Some pages are missing from the source. Topics from missing pages are not listed.
        </Notice>
      )}

      <Suspense fallback={<SkeletonLines lines={3} label="Loading lessons" />}>
        <Lessons chapterId={ch.id} topics={ch.topics} lang={lang} />
      </Suspense>

      <section aria-labelledby="topics-heading" className="space-y-3">
        <h2 id="topics-heading" className="text-lg font-semibold">
          Topics
        </h2>
        {ch.topics.length === 0 ? (
          <p className="text-muted">No topics are recorded for this chapter.</p>
        ) : (
          <ol className="divide-y divide-border rounded-xl border border-border bg-surface">
            {ch.topics.map((t) => (
              <TopicItem key={t.id} topic={t} />
            ))}
          </ol>
        )}
      </section>

      {ch.key_terms.length > 0 && (
        <section aria-labelledby="terms-heading" className="space-y-3">
          <h2 id="terms-heading" className="text-lg font-semibold">
            Key terms
          </h2>
          <ul className="flex flex-wrap gap-2">
            {ch.key_terms.slice(0, 40).map((term) => (
              <li key={term} className="rounded-full border border-border bg-surface px-3 py-1 text-sm">
                {term}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="source-heading" className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
        <h2 id="source-heading" className="font-semibold">
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
          {ch.slo_codes && !/not printed|unverified/i.test(ch.slo_codes) && (
            <>
              <dt className="text-muted">Learning outcome codes</dt>
              <dd>{ch.slo_codes}</dd>
            </>
          )}
          <dt className="text-muted">Source reference</dt>
          <dd className="font-mono text-xs">
            {ch.source.source_id} · PDF pages {pageRange(ch.source.pdf_start, ch.source.pdf_end)}
          </dd>
        </dl>
      </section>

      <nav aria-label="Chapter navigation" className="flex justify-between gap-3 text-sm">
        {ch.previous_chapter_id ? (
          <Link href={`/learn/chapter/${ch.previous_chapter_id}`} className="rounded-lg border border-border bg-surface px-4 py-2 hover:border-accent">
            ← Previous {bc.chapter_label.toLowerCase()}
          </Link>
        ) : (
          <span />
        )}
        {ch.next_chapter_id && (
          <Link href={`/learn/chapter/${ch.next_chapter_id}`} className="rounded-lg border border-border bg-surface px-4 py-2 hover:border-accent">
            Next {bc.chapter_label.toLowerCase()} →
          </Link>
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

const published = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium" });

async function Lessons({ chapterId, topics, lang }: { chapterId: string; topics: TopicNode[]; lang: string }) {
  const res = await getLessons(chapterId, lang);
  const lessons: Lesson[] = res.ok ? res.data : [];
  const token = await sessionToken();
  const doneRes = token && lessons.some((l) => !l.locked) ? await api<string[]>(`/v1/me/chapters/${encodeURIComponent(chapterId)}/completed-lessons`, { token }) : null;
  const done = new Set(doneRes?.ok ? doneRes.data : []);
  const titles = topicTitles(topics);
  return (
    <section aria-labelledby="lessons-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="lessons-heading" className="text-lg font-semibold">
          Lessons
        </h2>
        {lessons.length > 0 && (
          <nav aria-label="Lesson language" className="flex gap-1 text-sm">
            {LANGUAGES.map(([k, label]) => (
              <Link
                key={k}
                href={`/learn/chapter/${chapterId}${k === "en" ? "" : `?lang=${k}`}`}
                aria-current={k === lang ? "true" : undefined}
                lang={k === "ur" ? "ur" : "en"}
                className={`rounded-lg border px-3 py-1 ${k === lang ? "border-accent font-medium" : "border-border bg-surface hover:border-accent"}`}
              >
                {label}
              </Link>
            ))}
          </nav>
        )}
      </div>
      {lessons.length === 0 ? (
        <p className="text-muted">
          No reviewed lessons are published for this chapter yet. Lessons appear here only after an independent subject
          reviewer approves them. Until then, use the topic outline and your textbook pages below.
        </p>
      ) : (
        lessons.map((l) => (
          <article key={l.id} aria-labelledby={`lesson-${l.id}`} className="space-y-4 rounded-xl border border-border bg-surface p-5">
            {l.requested_language_missing && (
              <p className="rounded-lg bg-surface-muted px-3 py-2 text-sm">
                This lesson isn&apos;t available in {LANGUAGE_NAME[lang]} yet, so it&apos;s shown in {LANGUAGE_NAME[l.language]}.
              </p>
            )}
            <header className="space-y-1" lang={l.language === "ur" ? "ur" : "en"} dir={l.language === "ur" ? "rtl" : undefined}>
              <h3 id={`lesson-${l.id}`} className="text-xl font-semibold tracking-tight">
                {l.title}
              </h3>
              <p className="text-sm text-muted">
                {l.topic_id && titles.get(l.topic_id) ? `${titles.get(l.topic_id)} · ` : ""}
                {l.access_tier === "preview" ? "Free preview · " : ""}Reviewed lesson · version {l.version} ·
                published {published(l.published_at)}
              </p>
            </header>
            {l.locked || !l.body ? (
              <div className="rounded-lg bg-surface-muted p-4 text-sm">
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
                <LessonBlocks blocks={l.body.blocks as { type: string }[]} headingOffset={2} />
              </div>
            )}
            {token && !l.locked && l.body && (
              <form action={setLessonCompleted.bind(null, l.id, chapterId, !done.has(l.id))} className="flex flex-wrap items-center gap-3">
                <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium hover:border-accent">
                  {done.has(l.id) ? "✓ Completed: undo" : "Mark as completed"}
                </button>
                <span className="text-xs text-muted">Completion tracks your reading only. It isn&apos;t evidence of what you know.</span>
              </form>
            )}
            <p className="border-t border-border pt-3 text-sm text-muted">
              Textbook pages (PDF):{" "}
              {(l.source_refs as { pdf_from: number; pdf_to: number }[])
                .map((r) => (r.pdf_from === r.pdf_to ? `${r.pdf_from}` : `${r.pdf_from}–${r.pdf_to}`))
                .join(", ")}
            </p>
          </article>
        ))
      )}
    </section>
  );
}

function TopicItem({ topic }: { topic: TopicNode }) {
  const hasDetail = topic.children.length > 0 || topic.points.length > 0;
  const title = (
    <span className="flex flex-1 items-baseline gap-3">
      {topic.number ? (
        <span className="w-14 shrink-0 font-mono text-sm text-muted">{topic.number}</span>
      ) : (
        <span className="w-14 shrink-0" aria-hidden="true" />
      )}
      <span className="flex-1">{topic.title}</span>
      {topic.pdf_page != null && (
        <span title="Page index in the textbook PDF (may differ from the printed page number)">
          <Badge>PDF p. {topic.pdf_page}</Badge>
        </span>
      )}
    </span>
  );
  if (!hasDetail) return <li className="px-4 py-3">{title}</li>;
  return (
    <li>
      <details className="group px-4 py-3">
        <summary className="flex cursor-pointer list-none items-baseline gap-2">
          <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-90">
            ›
          </span>
          {title}
        </summary>
        <div className="mt-2 ml-6 space-y-2">
          {topic.points.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              {topic.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          {topic.children.length > 0 && (
            <ol className="divide-y divide-border rounded-lg border border-border">
              {topic.children.map((c) => (
                <TopicItem key={c.id} topic={c} />
              ))}
            </ol>
          )}
        </div>
      </details>
    </li>
  );
}
