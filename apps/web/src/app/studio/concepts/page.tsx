import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { Concept } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { STUDIO_ROLES } from "@/lib/studio";
import { NewConcept } from "./concept-forms";

export const metadata: Metadata = { title: "Concepts", robots: { index: false } };

// P05.S1.T2 (CONCEPTS-01): canonical learning outcomes mapped to the topics that teach them, with prerequisites.
export default function ConceptsPage({ searchParams }: PageProps<"/studio/concepts">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Concepts" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Concepts</h1>
        <p className="text-muted">
          Each learning outcome is written once and mapped to the topics that teach it, in Class XI and XII books alike. A concept is
          published only after an independent subject reviewer approves it with its source pages.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading concepts" />}>
        {searchParams.then((sp) => (
          <Board subject={typeof sp.subject === "string" ? sp.subject : ""} grade={typeof sp.grade === "string" ? sp.grade : ""} />
        ))}
      </Suspense>
    </div>
  );
}

async function Board({ subject, grade }: { subject: string; grade: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/studio/concepts");
  if (!user.me.roles.some((r) => STUDIO_ROLES.has(r))) return <Notice tone="warn" title="Staff only">Concepts are for content staff.</Notice>;
  const qs = new URLSearchParams();
  if (SUBJECTS.some(([c]) => c === subject)) qs.set("subject", subject);
  if (grade === "11" || grade === "12") qs.set("grade", grade);
  const res = await api<Concept[]>(`/v1/studio/concepts${qs.size ? `?${qs}` : ""}`, { token: user.token });
  const author = user.me.roles.includes("content_author");
  return (
    <div className="space-y-6">
      {author && (
        <section aria-labelledby="new-h" className="space-y-2">
          <h2 id="new-h" className="font-semibold">
            New concept
          </h2>
          <NewConcept subjects={SUBJECTS} />
        </section>
      )}
      <section aria-labelledby="list-h" className="space-y-3">
        <h2 id="list-h" className="font-semibold">
          Concepts in your subjects
        </h2>
        <form method="get" className="flex flex-wrap items-end gap-2 text-sm" aria-label="Filter concepts">
          <label className="flex flex-col gap-1">
            Subject
            <select name="subject" defaultValue={subject} className="rounded-lg border border-border bg-surface px-2 py-2">
              <option value="">All</option>
              {SUBJECTS.map(([c, n]) => (
                <option key={c} value={c}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Taught in
            <select name="grade" defaultValue={grade} className="rounded-lg border border-border bg-surface px-2 py-2">
              <option value="">Either class</option>
              <option value="11">Class XI</option>
              <option value="12">Class XII</option>
            </select>
          </label>
          <button type="submit" className="rounded-lg border border-border bg-surface px-3 py-2 hover:border-accent">
            Filter
          </button>
        </form>
        {!res.ok ? (
          <Notice tone="warn" title="Couldn't load concepts">
            {res.problem?.detail ?? "Please try again."}
          </Notice>
        ) : res.data.length === 0 ? (
          <p className="text-sm text-muted">No concepts yet.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {res.data.map((c) => (
              <li key={c.id} className="space-y-1 p-3">
                <p className="flex flex-wrap items-center gap-2">
                  <Link href={`/studio/concepts/${c.id}`} className="font-medium text-accent underline underline-offset-2">
                    {c.title}
                  </Link>
                  <Badge tone={c.status === "published" ? "ok" : "warn"}>{c.status}</Badge>
                  <span className="font-mono text-xs text-muted">{c.code}</span>
                </p>
                <p className="text-muted">
                  {c.subject.replace("_", " ")} · {c.topics.length} topic{c.topics.length === 1 ? "" : "s"} (
                  {[...new Set(c.topics.map((t) => GRADE_LABEL[t.grade]))].join(", ") || "not mapped"}) · {c.prerequisites.length} prerequisite
                  {c.prerequisites.length === 1 ? "" : "s"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
