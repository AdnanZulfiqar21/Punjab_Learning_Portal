import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { SearchHit } from "@portal/contracts";
import { searchContent } from "@/lib/api";
import { GRADE_LABEL, parseGrade } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { QuerySync } from "./query-sync";

export const metadata: Metadata = { title: "Search" };

const LANGUAGE_NAME: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };
const URDU_SCRIPT = /[؀-ۿ]/;

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Search" }]} />
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Search lessons, chapters and topics</h1>
      {/* One static form in the shell (never swapped), filled from the URL after hydration. */}
      <SearchForm />
      <Suspense fallback={null}>
        <QuerySync formId={FORM_ID} />
      </Suspense>
      <div className="mt-6">
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

function SearchForm() {
  return (
    <form id={FORM_ID} action="/search" method="get" role="search" className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
      <label className="sr-only" htmlFor="q">
        Search for
      </label>
      <input
        id="q"
        name="q"
        type="search"
        minLength={2}
        maxLength={100}
        required
        placeholder="e.g. photosynthesis, kinetic theory, matrices"
        className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-4 py-3"
      />
      <label className="sr-only" htmlFor="grade">
        Class
      </label>
      <select id="grade" name="grade" defaultValue="" className="rounded-lg border border-border bg-surface px-3 py-3">
        <option value="">Class XI and XII</option>
        <option value="11">Class XI only</option>
        <option value="12">Class XII only</option>
      </select>
      <label className="sr-only" htmlFor="subject">
        Subject
      </label>
      <select id="subject" name="subject" defaultValue="" className="rounded-lg border border-border bg-surface px-3 py-3">
        <option value="">All subjects</option>
        {SUBJECTS.map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
      <button type="submit" className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong dark:text-background">
        Search
      </button>
    </form>
  );
}

async function Results({ q, grade, subject }: { q: string; grade: string; subject: string }) {
  if (q.length < 2) return <p className="text-muted">Enter at least two characters.</p>;
  const g = parseGrade(grade) ?? undefined;
  const s = SUBJECTS.some(([code]) => code === subject) ? subject : undefined;
  const res = await searchContent(q, g, s);
  if (!res.ok) return <Notice tone="warn" title="Search is unavailable">{res.problem.detail}</Notice>;
  const { hits, also_searched: also = [] } = res.data;
  return (
    <section aria-label={`${hits.length} results`} className="space-y-3">
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
        <p className="text-muted">Nothing matches “{q}”. Try a shorter or different term.</p>
      ) : (
        <>
          <p className="text-sm text-muted">
            {hits.length} result{hits.length === 1 ? "" : "s"}
          </p>
          <ul className="space-y-2">
            {hits.map((h) => (
              <li key={`${h.kind}-${h.id}`}>{h.kind === "lesson" ? <LessonHit h={h} /> : <OutlineHit h={h} />}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

const card = "block rounded-xl border border-border bg-surface px-4 py-3 hover:border-accent";

function OutlineHit({ h }: { h: SearchHit }) {
  return (
    <Link href={`/learn/chapter/${h.chapter_id}`} className={card}>
      <span className="text-xs font-medium text-accent">
        {GRADE_LABEL[h.grade]} · {h.subject_name} · {h.kind === "chapter" ? "Chapter" : "Topic"}
      </span>
      <span className="block font-medium">
        {h.number && h.kind === "topic" && <span className="mr-2 font-mono text-sm text-muted">{h.number}</span>}
        {h.title}
      </span>
      {h.kind === "topic" && <span className="text-sm text-muted">in {h.chapter_title}</span>}
    </Link>
  );
}

// The chapter page shows this lesson (in this language) and checks publication and access again when it opens.
function LessonHit({ h }: { h: SearchHit }) {
  const lang = h.language ?? "en";
  const urdu = lang === "ur";
  const snippet = h.snippet ?? [];
  return (
    <Link href={`/learn/chapter/${h.chapter_id}${lang === "en" ? "" : `?lang=${lang}`}#lesson-${h.id}`} className={card}>
      <span className="text-xs font-medium text-accent">
        {GRADE_LABEL[h.grade]} · {h.subject_name} · Lesson{lang === "en" ? "" : ` (${LANGUAGE_NAME[lang] ?? lang})`}
        {h.access_tier === "preview" && " · Free preview"}
      </span>
      <span className="block font-medium" lang={urdu ? "ur" : undefined} dir={urdu ? "rtl" : undefined}>
        {h.title}
      </span>
      <span className="text-sm text-muted">in {h.chapter_title}</span>
      {h.locked ? (
        <span className="mt-1 block text-sm text-muted">Included with a plan or the free 30-day trial. Found by its title.</span>
      ) : (
        snippet.length > 0 && (
          <span className="mt-1 block text-sm" lang={urdu ? "ur" : undefined} dir={urdu ? "rtl" : undefined}>
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
    </Link>
  );
}
