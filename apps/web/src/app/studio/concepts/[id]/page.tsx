import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import type { Concept, SourceInfo, TopicNode } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { getBookFor, getChapter } from "@/lib/api";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser } from "@/lib/session";
import { STUDIO_ROLES } from "@/lib/studio";
import { EditConcept, Prerequisites, PublishConcept, TopicPicker } from "../concept-forms";

export const metadata: Metadata = { title: "Concept", robots: { index: false } };
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function flatten(nodes: TopicNode[], out: { id: string; label: string }[] = []) {
  for (const n of nodes) {
    out.push({ id: n.id, label: n.number ? `${n.number} ${n.title}` : n.title });
    flatten(n.children, out);
  }
  return out;
}

export default function ConceptPage({ params, searchParams }: PageProps<"/studio/concepts/[id]">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { href: "/studio/concepts", label: "Concepts" }, { label: "Concept" }]} />
      <Suspense fallback={<SkeletonLines lines={8} label="Loading concept" />}>
        {Promise.all([params, searchParams]).then(([{ id }, sp]) => (
          <Detail id={id} grade={sp.grade === "12" ? 12 : 11} chapter={typeof sp.chapter === "string" ? sp.chapter : ""} />
        ))}
      </Suspense>
    </div>
  );
}

async function Detail({ id, grade, chapter }: { id: string; grade: 11 | 12; chapter: string }) {
  if (!UUID.test(id)) notFound();
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/studio/concepts/${id}`);
  if (!user.me.roles.some((r) => STUDIO_ROLES.has(r))) return <Notice tone="warn" title="Staff only">Concepts are for content staff.</Notice>;
  const res = await api<Concept>(`/v1/studio/concepts/${id}`, { token: user.token });
  if (!res.ok) notFound();
  const c = res.data;
  const author = user.me.roles.includes("content_author");
  const reviewer = user.me.roles.includes("subject_reviewer");
  const editable = c.status === "draft" && author;
  const [all, sources, book] = await Promise.all([
    api<Concept[]>(`/v1/studio/concepts?subject=${encodeURIComponent(c.subject)}`, { token: user.token }),
    api<SourceInfo[]>("/v1/studio/sources", { token: user.token }),
    getBookFor(grade, c.subject),
  ]);
  const chapters = book.ok ? book.data.chapters : [];
  const chosenChapter = chapters.find((ch) => ch.id === chapter) ?? chapters[0];
  const chapterData = chosenChapter && UUID.test(chosenChapter.id) ? await getChapter(chosenChapter.id) : null;
  const topics = chapterData?.ok ? flatten(chapterData.data.topics) : [];
  const others = all.ok ? all.data.filter((x) => x.id !== c.id) : [];
  const label = (cid: string) => {
    const x = others.find((o) => o.id === cid);
    return x ? `${x.title} (${x.code})` : cid;
  };
  return (
    <article className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{c.title}</h1>
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span className="font-mono">{c.code}</span> · {c.subject.replace("_", " ")}
          <Badge tone={c.status === "published" ? "ok" : "warn"}>{c.status}</Badge>
        </p>
        <p>{c.statement}</p>
      </div>

      {editable && (
        <section aria-labelledby="edit-h" className="space-y-2">
          <h2 id="edit-h" className="font-semibold">
            Edit the draft
          </h2>
          <EditConcept
            id={c.id}
            title={c.title}
            statement={c.statement}
            refs={c.source_refs as { source_document_id: string; pdf_from: number; pdf_to: number }[]}
            sources={(sources.ok ? sources.data : []).filter((s) => s.subject_code === c.subject).map((s) => ({ id: s.id, label: `${s.source_id} (${GRADE_LABEL[s.grade_number]})` }))}
          />
        </section>
      )}

      <section aria-labelledby="topics-h" className="space-y-2">
        <h2 id="topics-h" className="font-semibold">
          Taught in these topics
        </h2>
        {c.topics.length === 0 ? (
          <p className="text-sm text-muted">Not mapped to any topic yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {c.topics.map((t) => (
              <li key={t.topic_id}>
                {GRADE_LABEL[t.grade]} · Chapter {t.chapter_number} · {t.number ? `${t.number} ` : ""}
                {t.title}
              </li>
            ))}
          </ul>
        )}
        {editable && (
          <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
            <nav aria-label="Choose a book and chapter" className="flex flex-wrap gap-2 text-sm">
              {[11, 12].map((g) => (
                <Link key={g} href={`/studio/concepts/${c.id}?grade=${g}`} aria-current={g === grade ? "true" : undefined} className={`rounded-lg border px-3 py-1 ${g === grade ? "border-accent font-medium" : "border-border"}`}>
                  {GRADE_LABEL[g]}
                </Link>
              ))}
            </nav>
            <div className="flex flex-wrap gap-1 text-xs">
              {chapters.map((ch) => (
                <Link key={ch.id} href={`/studio/concepts/${c.id}?grade=${grade}&chapter=${ch.id}`} aria-current={ch.id === chosenChapter?.id ? "true" : undefined} className={`rounded border px-2 py-1 ${ch.id === chosenChapter?.id ? "border-accent font-medium" : "border-border"}`}>
                  Ch {ch.number}
                </Link>
              ))}
            </div>
            {chosenChapter && <p className="text-sm font-medium">{`${GRADE_LABEL[grade]} · Chapter ${chosenChapter.number}: ${chosenChapter.title}`}</p>}
            <TopicPicker id={c.id} mapped={c.topics.map((t) => t.topic_id)} chapterTopics={topics} />
          </div>
        )}
      </section>

      <section aria-labelledby="prereq-h" className="space-y-2">
        <h2 id="prereq-h" className="font-semibold">
          Prerequisites
        </h2>
        <Prerequisites
          id={c.id}
          current={c.prerequisites.map((p) => ({ id: p.requires_id, label: label(p.requires_id) }))}
          options={others.filter((o) => o.status !== "retired" && !c.prerequisites.some((p) => p.requires_id === o.id)).map((o) => ({ id: o.id, label: `${o.title} (${o.code})` }))}
          editable={author}
        />
      </section>

      {c.status === "draft" && reviewer && (
        <section aria-labelledby="publish-h" className="space-y-2">
          <h2 id="publish-h" className="font-semibold">
            Independent review
          </h2>
          <p className="text-sm text-muted">Check the outcome against the cited source pages. You can&apos;t publish a concept you wrote.</p>
          <PublishConcept id={c.id} />
        </section>
      )}
    </article>
  );
}
