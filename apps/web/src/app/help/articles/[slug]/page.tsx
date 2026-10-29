import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { HelpArticle } from "@portal/contracts";
import { LessonBlocks } from "@/components/lesson-blocks";
import { IconTile, PageIcon } from "@/components/learner-pages";
import { Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";

export const metadata: Metadata = { title: "Help" };

export default function HelpArticlePage({ params }: PageProps<"/help/articles/[slug]">) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link href="/help/articles" className="inline-flex min-h-11 items-center gap-1.5 rounded-full text-sm font-medium text-accent underline-offset-2 hover:underline">
        <PageIcon name="arrow-left" size={16} />
        All help articles
      </Link>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading the article" />}>
        {params.then(({ slug }) => (
          <Article slug={slug} />
        ))}
      </Suspense>
    </div>
  );
}

// DESIGN-01: the title on a glass header card; the article's text on the solid surface (reading text never sits on glass).
async function Article({ slug }: { slug: string }) {
  if (!/^[a-z0-9-]{2,80}$/.test(slug)) notFound();
  const res = await api<HelpArticle>(`/v1/help/articles/${slug}`);
  if (!res.ok) notFound();
  const a = res.data;
  return (
    <article className="space-y-4">
      <header className="glass flex items-center gap-4 rounded-card px-6 py-6 sm:px-8">
        <IconTile icon="file-text" size={48} />
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-semibold tracking-[0.15em] text-accent uppercase">Help article</p>
          <h1 className="font-display text-[26px] leading-8 font-bold tracking-tight break-words sm:text-[32px] sm:leading-10">{a.title}</h1>
        </div>
      </header>
      <div className="space-y-4 rounded-card border border-border bg-surface px-5 py-6 sm:px-9 sm:py-8">
        {a.fallback_locale && <Notice title="Shown in English">This article isn&apos;t available in your language yet.</Notice>}
        <LessonBlocks blocks={(a.body as { blocks: { type: string }[] }).blocks as never} />
        <p className="border-t border-border pt-4 text-xs text-muted">Version {a.version}</p>
      </div>
    </article>
  );
}
