import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { NotebookEntry } from "@portal/contracts";
import { LessonBlocks } from "@/components/lesson-blocks";
import { typesetEquations } from "@/lib/typeset";
import { MockRunningNotice } from "@/components/mock-running";
import { GlassCard } from "@/components/glass-card";
import { PageHero } from "@/components/page-hero";
import { PracticeIcon } from "@/components/practice-ui";
import { SectionHeader } from "@/components/section-header";
import { StatChip } from "@/components/stat-chip";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser } from "@/lib/session";
import { NoteEditor, StartReview } from "./controls";

export const metadata: Metadata = { title: "Mistake notebook", robots: { index: false } };

export default function NotebookPage() {
  return (
    <div className="space-y-8">
      <div>
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Mistake notebook" }]} />
        <PageHero
          align="start"
          eyebrow="Practice · Review"
          title="Mistake notebook"
          lead="Questions you answered wrongly, and questions you flagged as unsure, come back for review after 1, 3, 7 and 14 days. Get one right at every step without flagging it and it's marked as mastered; miss it again and it starts over."
          backdrop={<span aria-hidden="true" className="pointer-events-none absolute inset-0 bg-accent-soft opacity-50" />}
        />
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your notebook" />}>
        <Entries />
      </Suspense>
    </div>
  );
}

async function Entries() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/notebook");
  const res = await api<NotebookEntry[]>("/v1/me/notebook", { token: user.token });
  if (!res.ok) {
    const p = res.problem as { code_reason?: string; attempt_id?: string } | null;
    if (p?.code_reason === "MOCK_IN_PROGRESS" && p.attempt_id) return <MockRunningNotice attemptId={p.attempt_id} />;
    return <Notice tone="warn" title="Couldn't load your notebook">{res.problem?.detail ?? "Please try again."}</Notice>;
  }
  if (res.data.length === 0) {
    return (
      <Notice title="Nothing here yet">
        Questions you get wrong or flag as unsure in a practice test appear here.{" "}
        <Link href="/practice" className="font-medium text-accent underline underline-offset-2">
          Build a practice test
        </Link>
        .
      </Notice>
    );
  }
  const due = new Map<string, number>();
  for (const e of res.data) if (e.due) due.set(`${e.grade}:${e.subject}`, (due.get(`${e.grade}:${e.subject}`) ?? 0) + 1);
  return (
    <div className="space-y-8">
      <p className="flex flex-wrap gap-2">
        <StatChip>
          <PracticeIcon name="bookmark" size={16} className="text-accent" />
          {res.data.length} {res.data.length === 1 ? "entry" : "entries"}
        </StatChip>
        <StatChip>
          <PracticeIcon name="calendar" size={16} className="text-accent" />
          {res.data.filter((e) => e.due).length} due now
        </StatChip>
      </p>
      {due.size > 0 && (
        <GlassCard as="section" aria-labelledby="due-h" className="space-y-3">
          <h2 id="due-h" className="font-display text-lg font-semibold">
            Due for review
          </h2>
          <ul className="divide-y divide-border">
            {[...due.entries()].map(([key, n]) => {
              const [grade, subject] = key.split(":");
              return (
                <li key={key} className="flex flex-wrap items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <span className="font-medium capitalize">
                    {GRADE_LABEL[Number(grade)]} {subject.replace("_", " ")}: {n} due
                  </span>
                  <StartReview grade={Number(grade)} subject={subject} />
                </li>
              );
            })}
          </ul>
        </GlassCard>
      )}
      <section aria-labelledby="entries-h">
        <SectionHeader id="entries-h" title="Your entries" />
        <ol className="space-y-4" aria-label="Notebook entries">
        {res.data.map((e) => (
          // The question itself is read on a solid surface (owner rule 5).
          <li key={e.id} className="space-y-3 rounded-card border border-border bg-surface p-5 text-sm shadow-glass">
            <p className="flex flex-wrap items-center gap-2">
              <Badge tone={e.status === "mastered" ? "ok" : e.status === "voided" ? "info" : e.due ? "warn" : "info"}>
                {e.status === "open" ? (e.due ? "Due now" : "Waiting") : e.status}
              </Badge>
              <span className="text-muted">
                {GRADE_LABEL[e.grade]} {e.subject.replace("_", " ")}
                {e.misses > 0 ? ` · missed ${e.misses} time${e.misses === 1 ? "" : "s"}` : ""}
                {/* NOTEBOOK-FLAGS-01: collected because the learner flagged it as unsure, even if the answer was right. */}
                {e.flagged ? " · you flagged it as unsure" : ""}
              </span>
              <Link href={`/practice/attempt/${e.source_attempt_id}/result`} className="text-accent underline underline-offset-2">
                See the original question {e.position}
              </Link>
            </p>
            <LessonBlocks blocks={e.stem as { type: string }[]} typeset={typesetEquations(e.stem as { type: string }[])} headingOffset={2} assetUrl={(v) => `/practice/attempt/${e.source_attempt_id}/assets/${v}`} />
            <p className="text-muted">{e.why}</p>
            <NoteEditor id={e.id} initial={e.note} />
          </li>
        ))}
        </ol>
      </section>
    </div>
  );
}
