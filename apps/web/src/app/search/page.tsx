import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { searchCatalogue } from "@/lib/api";
import { GRADE_LABEL, parseGrade } from "@/lib/format";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";

export const metadata: Metadata = { title: "Search" };

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <div>
      <Breadcrumbs items={[{ href: "/", label: "Home" }, { label: "Search" }]} />
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Search chapters and topics</h1>
      <Suspense fallback={<SearchForm q="" grade="" />}>
        {searchParams.then((sp) => (
          <SearchForm q={one(sp.q)} grade={one(sp.grade)} />
        ))}
      </Suspense>
      <div className="mt-6">
        <Suspense fallback={<SkeletonLines lines={5} label="Searching" />}>
          {searchParams.then((sp) => (
            <Results q={one(sp.q)} grade={one(sp.grade)} />
          ))}
        </Suspense>
      </div>
    </div>
  );
}

function one(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

function SearchForm({ q, grade }: { q: string; grade: string }) {
  return (
    <form action="/search" method="get" role="search" className="flex flex-col gap-3 sm:flex-row">
      <label className="sr-only" htmlFor="q">
        Topic or chapter
      </label>
      <input
        id="q"
        name="q"
        type="search"
        defaultValue={q}
        minLength={2}
        maxLength={100}
        required
        placeholder="e.g. photosynthesis, kinetic theory, matrices"
        className="flex-1 rounded-lg border border-border bg-surface px-4 py-3"
      />
      <label className="sr-only" htmlFor="grade">
        Class
      </label>
      <select id="grade" name="grade" defaultValue={grade} className="rounded-lg border border-border bg-surface px-3 py-3">
        <option value="">Class XI and XII</option>
        <option value="11">Class XI only</option>
        <option value="12">Class XII only</option>
      </select>
      <button type="submit" className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong dark:text-background">
        Search
      </button>
    </form>
  );
}

async function Results({ q, grade }: { q: string; grade: string }) {
  if (q.length < 2) return <p className="text-muted">Enter at least two characters.</p>;
  const g = parseGrade(grade) ?? undefined;
  const res = await searchCatalogue(q, g);
  if (!res.ok) return <Notice tone="warn" title="Search is unavailable">{res.problem.detail}</Notice>;
  const hits = res.data.hits;
  if (hits.length === 0) {
    return <p className="text-muted">No chapters or topics match “{q}”. Try a shorter or different term.</p>;
  }
  return (
    <section aria-label={`${hits.length} results`}>
      <p className="mb-3 text-sm text-muted">
        {hits.length} result{hits.length === 1 ? "" : "s"}
      </p>
      <ul className="space-y-2">
        {hits.map((h) => (
          <li key={`${h.kind}-${h.id}`}>
            <Link
              href={`/learn/chapter/${h.chapter_id}`}
              className="block rounded-xl border border-border bg-surface px-4 py-3 hover:border-accent"
            >
              <span className="text-xs font-medium text-accent">
                {GRADE_LABEL[h.grade]} · {h.subject_name} · {h.kind === "chapter" ? "Chapter" : "Topic"}
              </span>
              <span className="block font-medium">
                {h.number && h.kind === "topic" && <span className="mr-2 font-mono text-sm text-muted">{h.number}</span>}
                {h.title}
              </span>
              {h.kind === "topic" && <span className="text-sm text-muted">in {h.chapter_title}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
