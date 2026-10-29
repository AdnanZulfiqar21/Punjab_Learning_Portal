import type { Metadata } from "next";
import { Suspense } from "react";
import type { SearchHit } from "@portal/contracts";
import { searchContent } from "@/lib/api";
import { GRADE_LABEL, parseGrade } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { buttonClasses } from "@/components/button";
import { GlassCardLink } from "@/components/glass-card";
import { Icon, SubjectIcon } from "@/components/icons";
import { PageIcon } from "@/components/learner-pages";
import { PageHero } from "@/components/page-hero";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { subjectKey } from "@/lib/learn-context";
import { QuerySync } from "./query-sync";

export const metadata: Metadata = { title: "Search" };

const LANGUAGE_NAME: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };
const URDU_SCRIPT = /[؀-ۿ]/;
// The filter offers the four taught subjects (owner rule: Mathematics is not shown as a taught subject); a URL that
// already names mathematics still filters by it.
const FILTER_SUBJECTS = SUBJECTS.filter(([code]) => code !== "mathematics");

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Search" }]} />
      <PageHero
        eyebrow="Class 11 · Class 12"
        title="Search lessons, chapters and topics"
        lead="Search in English, Urdu or Roman Urdu. Results show the class and subject of each chapter, topic and lesson."
        className="pt-4! sm:pt-8!"
      />
      {/* One static form in the shell (never swapped), filled from the URL after hydration. */}
      <div className="mx-auto max-w-3xl">
        <SearchForm />
      </div>
      <Suspense fallback={null}>
        <QuerySync formId={FORM_ID} />
      </Suspense>
      <div className="mx-auto mt-8 max-w-3xl">
        <Suspense fallback={<SkeletonLines lines={5} label="Searching" />}>
          {searchParams.then((sp) => (
            <Results q={one(sp.q)} grade={one(sp.grade)} subject={one(sp.subject)} />
          ))}
        </Suspense>
      </div>
    </div>
  );
}

function one(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

const FORM_ID = "catalogue-search";

const chip =
  "min-h-11 cursor-pointer appearance-none rounded-full border border-border bg-surface py-2 pr-10 pl-10 text-sm font-medium text-foreground transition duration-200 hover:border-accent focus-visible:border-accent";

function SearchForm() {
  return (
    <form id={FORM_ID} action="/search" method="get" role="search" className="glass space-y-4 rounded-card p-3 sm:p-4">
      <div className="relative">
        <label className="sr-only" htmlFor="q">
          Search for
        </label>
        <Icon name="search" size={22} className="pointer-events-none absolute top-1/2 left-5 -translate-y-1/2 text-muted" />
        <input
          id="q"
          name="q"
          type="search"
          minLength={2}
          maxLength={100}
          required
          placeholder="e.g. photosynthesis, kinetic theory, arrays"
          className="h-14 w-full min-w-0 rounded-full border border-border bg-surface pr-16 pl-14 text-base text-foreground shadow-glass transition duration-200 hover:border-accent/60 focus-visible:border-accent sm:pr-36 sm:text-lg"
        />
        <button type="submit" className={buttonClasses({ className: "absolute top-1.5 right-1.5 w-11 px-0! sm:w-auto sm:px-5!" })}>
          <span className="sr-only sm:not-sr-only">Search</span>
          <Icon name="arrow-right" size={18} className="sm:hidden" />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2 px-1">
        <span className="flex items-center gap-1.5 pr-1 text-sm text-muted">
          <PageIcon name="funnel" size={16} />
          Filters
        </span>
        <span className="relative inline-flex">
          <label className="sr-only" htmlFor="grade">
            Class
          </label>
          <PageIcon name="graduation-cap" size={16} className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-accent" />
          <select id="grade" name="grade" defaultValue="" className={chip}>
            <option value="">Class 11 and 12</option>
            <option value="11">Class 11 only</option>
            <option value="12">Class 12 only</option>
          </select>
          <PageIcon name="chevron-down" size={16} className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-muted" />
        </span>
        <span className="relative inline-flex">
          <label className="sr-only" htmlFor="subject">
            Subject
          </label>
          <Icon name="book-open" size={16} className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-accent" />
          <select id="subject" name="subject" defaultValue="" className={chip}>
            <option value="">All subjects</option>
            {FILTER_SUBJECTS.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
          <PageIcon name="chevron-down" size={16} className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-muted" />
        </span>
      </div>
    </form>
  );
}

async function Results({ q, grade, subject }: { q: string; grade: string; subject: string }) {
  if (q.length < 2) return <p className="text-center text-muted">Enter at least two characters.</p>;
  const g = parseGrade(grade) ?? undefined;
  const s = SUBJECTS.some(([code]) => code === subject) ? subject : undefined;
  const res = await searchContent(q, g, s);
  if (!res.ok) return <Notice tone="warn" title="Search is unavailable">{res.problem.detail}</Notice>;
  const { hits, also_searched: also = [] } = res.data;
  return (
    <section aria-label={`${hits.length} results`} className="space-y-4">
      {also.length > 0 && (
        <p className="text-sm text-muted">
          Also searched for{" "}
          {also.map((t, i) => (
            <span key={t}>
              {i > 0 && ", "}
              <span lang={URDU_SCRIPT.test(t) ? "ur" : undefined} dir={URDU_SCRIPT.test(t) ? "rtl" : undefined} className="font-medium text-foreground">
                {t}
              </span>
            </span>
          ))}{" "}
          (the same term in English, Urdu or Roman Urdu).
        </p>
      )}
      {hits.length === 0 ? (
        <p className="glass rounded-card p-[22px] text-center text-muted">Nothing matches “{q}”. Try a shorter or different term.</p>
      ) : (
        <>
          <p className="text-sm font-medium text-muted">
            {hits.length} result{hits.length === 1 ? "" : "s"}
          </p>
          <ul className="space-y-3">
            {hits.map((h) => (
              <li key={`${h.kind}-${h.id}`} data-subject={subjectKey(h.subject_code)}>
                {h.kind === "lesson" ? <LessonHit h={h} /> : <OutlineHit h={h} />}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

// A glass card per result: the subject's tile, then the class · subject · kind line, the title and where it is.
const card = "flex items-start gap-4";
const body = "min-w-0 flex-1 space-y-0.5";

function OutlineHit({ h }: { h: SearchHit }) {
  return (
    <GlassCardLink href={`/learn/chapter/${h.chapter_id}`} className={card}>
      <SubjectIcon subject={h.subject_code} size={40} />
      <span className={body}>
        <span className="block text-xs font-semibold text-accent">
          {GRADE_LABEL[h.grade]} · {h.subject_name} · {h.kind === "chapter" ? "Chapter" : "Topic"}
        </span>
        <span className="block font-display text-[17px] font-semibold text-foreground">
          {h.number && h.kind === "topic" && <span className="mr-2 font-mono text-sm text-muted">{h.number}</span>}
          {h.title}
        </span>
        {h.kind === "topic" && <span className="block text-sm text-muted">in {h.chapter_title}</span>}
      </span>
      <Icon name="chevron-right" size={18} className="mt-1 shrink-0 text-muted" />
    </GlassCardLink>
  );
}

// The chapter page shows this lesson (in this language) and checks publication and access again when it opens.
function LessonHit({ h }: { h: SearchHit }) {
  const lang = h.language ?? "en";
  const urdu = lang === "ur";
  const snippet = h.snippet ?? [];
  return (
    <GlassCardLink href={`/learn/chapter/${h.chapter_id}${lang === "en" ? "" : `?lang=${lang}`}#lesson-${h.id}`} className={card}>
      <SubjectIcon subject={h.subject_code} size={40} />
      <span className={body}>
      <span className="block text-xs font-semibold text-accent">
        {GRADE_LABEL[h.grade]} · {h.subject_name} · Lesson{lang === "en" ? "" : ` (${LANGUAGE_NAME[lang] ?? lang})`}
        {h.access_tier === "preview" && " · Free preview"}
      </span>
      <span className="block font-display text-[17px] font-semibold text-foreground" lang={urdu ? "ur" : undefined} dir={urdu ? "rtl" : undefined}>
        {h.title}
      </span>
      <span className="block text-sm text-muted">in {h.chapter_title}</span>
      {h.locked ? (
        <span className="mt-1.5 flex items-center gap-1.5 text-sm text-muted">
          <PageIcon name="lock" size={14} className="shrink-0" />
          Included with a plan or the free 30-day trial. Found by its title.
        </span>
      ) : (
        snippet.length > 0 && (
          <span className="mt-1.5 block text-sm text-foreground" lang={urdu ? "ur" : undefined} dir={urdu ? "rtl" : undefined}>
            {snippet.map((p, i) =>
              p.match ? (
                <mark key={i} className="rounded bg-accent-soft px-0.5 text-foreground">
                  {p.text}
                </mark>
              ) : (
                <span key={i}>{p.text}</span>
              ),
            )}
          </span>
        )
      )}
      </span>
      <Icon name="chevron-right" size={18} className="mt-1 shrink-0 text-muted" />
    </GlassCardLink>
  );
}
