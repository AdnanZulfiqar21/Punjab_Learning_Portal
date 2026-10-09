import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { HelpArticleSummary } from "@portal/contracts";
import { Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";

export const metadata: Metadata = { title: "Help articles" };

// P15.S2.T1: published help articles, searchable without signing in.
export default function HelpArticlesPage({ searchParams }: PageProps<"/help/articles">) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Help articles</h1>
      <form role="search" className="flex gap-2">
        <label htmlFor="help-q" className="sr-only">
          Search help
        </label>
        <input id="help-q" name="q" placeholder="Search help, e.g. upload limits" className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2" />
        <button type="submit" className="rounded-lg border border-border px-4 py-2 font-medium">
          Search
        </button>
      </form>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading help articles" />}>
        {searchParams.then((sp) => (
          <Results q={typeof sp.q === "string" ? sp.q : ""} />
        ))}
      </Suspense>
      <p className="text-sm text-muted">
        Can&apos;t find an answer? <Link href="/help/new" className="text-accent underline">Ask for help</Link>.
      </p>
    </div>
  );
}

async function Results({ q }: { q: string }) {
  const res = await api<HelpArticleSummary[]>(`/v1/help/articles?q=${encodeURIComponent(q)}`);
  if (!res.ok) return <Notice tone="warn" title="Help is unavailable right now">Try again in a moment.</Notice>;
  if (res.data.length === 0) return <Notice title="No matching articles">{q ? `Nothing matches “${q}”.` : "No help articles are published yet."}</Notice>;
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Help articles">
      {res.data.map((a) => (
        <li key={a.slug} className="px-4 py-3">
          <Link href={`/help/articles/${a.slug}`} className="font-medium text-accent underline-offset-2 hover:underline">
            {a.title}
          </Link>
          <p className="text-sm text-muted">{a.summary}</p>
        </li>
      ))}
    </ul>
  );
}
