import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { HelpArticleSummary } from "@portal/contracts";
import { buttonClasses } from "@/components/button";
import { GlassCard, GlassCardLink } from "@/components/glass-card";
import { Icon } from "@/components/icons";
import { IconTile } from "@/components/learner-pages";
import { PageHero } from "@/components/page-hero";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";

export const metadata: Metadata = { title: "Help articles" };

// P15.S2.T1: published help articles, searchable without signing in.
export default function HelpArticlesPage({ searchParams }: PageProps<"/help/articles">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/help", label: "Help" }, { label: "Help articles" }]} />
      <PageHero eyebrow="Help" title="Help articles" lead="Published answers to common questions. You can search them without signing in." className="pt-2! sm:pt-6!" />
      <div className="mx-auto max-w-3xl space-y-6">
        <form role="search" className="glass relative rounded-full p-1.5">
          <label htmlFor="help-q" className="sr-only">
            Search help
          </label>
          <Icon name="search" size={20} className="pointer-events-none absolute top-1/2 left-5 -translate-y-1/2 text-muted" />
          <input
            id="help-q"
            name="q"
            placeholder="Search help, e.g. upload limits"
            className="h-12 w-full min-w-0 rounded-full border border-border bg-surface pr-28 pl-11 text-foreground transition duration-200 hover:border-accent/60 focus-visible:border-accent"
          />
          <button type="submit" className={buttonClasses({ className: "absolute top-1/2 right-3 -translate-y-1/2" })}>
            Search
          </button>
        </form>
        <Suspense fallback={<SkeletonLines lines={5} label="Loading help articles" />}>
          {searchParams.then((sp) => (
            <Results q={typeof sp.q === "string" ? sp.q : ""} />
          ))}
        </Suspense>
        <GlassCard className="text-center text-sm text-muted">
          Can&apos;t find an answer?{" "}
          <Link href="/help/new" className="font-medium text-accent underline underline-offset-2">
            Ask for help
          </Link>
          .
        </GlassCard>
      </div>
    </div>
  );
}

async function Results({ q }: { q: string }) {
  const res = await api<HelpArticleSummary[]>(`/v1/help/articles?q=${encodeURIComponent(q)}`);
  if (!res.ok) return <Notice tone="warn" title="Help is unavailable right now">Try again in a moment.</Notice>;
  if (res.data.length === 0) return <Notice title="No matching articles">{q ? `Nothing matches “${q}”.` : "No help articles are published yet."}</Notice>;
  return (
    <ul className="space-y-3" aria-label="Help articles">
      {res.data.map((a) => (
        <li key={a.slug}>
          <GlassCardLink href={`/help/articles/${a.slug}`} className="flex items-start gap-4">
            <IconTile icon="file-text" />
            <span className="min-w-0 flex-1 space-y-0.5">
              <span className="block font-display text-[17px] font-semibold text-accent">{a.title}</span>
              <span className="block text-sm text-muted">{a.summary}</span>
            </span>
            <Icon name="chevron-right" size={18} className="mt-1 shrink-0 text-muted" />
          </GlassCardLink>
        </li>
      ))}
    </ul>
  );
}
