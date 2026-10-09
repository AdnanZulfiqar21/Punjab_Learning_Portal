import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { HelpArticle } from "@portal/contracts";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";

export const metadata: Metadata = { title: "Help" };

export default function HelpArticlePage({ params }: PageProps<"/help/articles/[slug]">) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link href="/help/articles" className="text-sm text-accent underline-offset-2 hover:underline">
        ← All help articles
      </Link>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading the article" />}>
        {params.then(({ slug }) => (
          <Article slug={slug} />
        ))}
      </Suspense>
    </div>
  );
}

async function Article({ slug }: { slug: string }) {
  if (!/^[a-z0-9-]{2,80}$/.test(slug)) notFound();
  const res = await api<HelpArticle>(`/v1/help/articles/${slug}`);
  if (!res.ok) notFound();
  const a = res.data;
  return (
    <article className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">{a.title}</h1>
      {a.fallback_locale && <Notice title="Shown in English">This article isn&apos;t available in your language yet.</Notice>}
      <LessonBlocks blocks={(a.body as { blocks: { type: string }[] }).blocks as never} />
      <p className="text-xs text-muted">Version {a.version}</p>
    </article>
  );
}
