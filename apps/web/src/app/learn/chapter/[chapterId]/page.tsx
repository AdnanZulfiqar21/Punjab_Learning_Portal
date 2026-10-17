import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { FavouriteTopic, TopicNode } from "@portal/contracts";
import { FavouriteButton } from "@/components/study-tools";
import { getChapter } from "@/lib/api";
import { GRADE_LABEL } from "@/lib/format";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, sessionToken } from "@/lib/session";

export const metadata: Metadata = { title: "Chapter" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function ChapterPage({ params }: PageProps<"/learn/chapter/[chapterId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading chapter" />}>
      {params.then(({ chapterId }) => <ChapterView id={chapterId} />)}
    </Suspense>
  );
}

async function ChapterView({ id }: { id: string }) {
  if (!UUID.test(id)) notFound();
  const res = await getChapter(id);
  if (!res.ok) notFound();
  const ch = res.data;
  const bc = ch.breadcrumb;
  const gradeLabel = GRADE_LABEL[bc.grade.number];
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

      {ch.status !== "complete" && (
        <Notice tone="warn" title={`This chapter is ${ch.status} in the supplied textbook file`}>
          Some pages are missing from the source. Topics from missing pages are not listed.
        </Notice>
      )}

      <section aria-labelledby="topics-heading" className="space-y-3">
        <h2 id="topics-heading" className="text-lg font-semibold">
          Topics
        </h2>
        {ch.topics.length === 0 ? (
          <p className="text-muted">No topics are recorded for this chapter.</p>
        ) : (
          <Suspense fallback={<TopicList topics={ch.topics} favourites={null} />}>
            <Topics topics={ch.topics} />
          </Suspense>
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

async function Topics({ topics }: { topics: TopicNode[] }) {
  const token = await sessionToken();
  const res = token ? await api<FavouriteTopic[]>("/v1/me/favourites", { token }) : null;
  return <TopicList topics={topics} favourites={res?.ok ? new Set(res.data.map((f) => f.topic_id)) : null} />;
}

function TopicList({ topics, favourites }: { topics: TopicNode[]; favourites: Set<string> | null }) {
  return (
    <ol className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
      {topics.map((t) => (
        <TopicItem key={t.id} topic={t} favourites={favourites} />
      ))}
    </ol>
  );
}

function TopicItem({ topic, favourites }: { topic: TopicNode; favourites: Set<string> | null }) {
  const title = (
    <Link href={`/learn/topic/${topic.id}`} className="flex min-w-0 flex-1 items-baseline gap-3 hover:text-accent">
      {topic.number && <span className="w-12 shrink-0 font-mono text-sm text-muted">{topic.number}</span>}
      <span className="font-medium">{topic.title}</span>
    </Link>
  );
  const star = favourites && (
    <FavouriteButton topicId={topic.id} label={topic.number ? `${topic.number} ${topic.title}` : topic.title} initial={favourites.has(topic.id)} />
  );
  const hasDetail = topic.points.length > 0 || topic.children.length > 0;
  if (!hasDetail) {
    return (
      <li className="flex items-start gap-2 px-4 py-3">
        {title}
        {star}
      </li>
    );
  }
  return (
    <li className="flex items-start gap-2 pr-4">
      <details className="group flex-1 py-3 pl-4">
        <summary className="flex cursor-pointer list-none items-baseline gap-2">
          {title}
          <span className="text-sm text-muted">Outline</span>
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
                <TopicItem key={c.id} topic={c} favourites={favourites} />
              ))}
            </ol>
          )}
        </div>
      </details>
      <span className="pt-2.5">{star}</span>
    </li>
  );
}
