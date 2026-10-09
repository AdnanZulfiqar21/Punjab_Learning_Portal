import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { NotebookEntry } from "@portal/contracts";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser } from "@/lib/session";
import { NoteEditor, StartReview } from "./controls";

export const metadata: Metadata = { title: "Mistake notebook", robots: { index: false } };

export default function NotebookPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Mistake notebook" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mistake notebook</h1>
        <p className="text-muted">
          Questions you answered wrongly come back for review after 1, 3, 7 and 14 days. Get one right at every step and it&apos;s marked as mastered; miss it again and it starts over.
        </p>
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
  if (!res.ok) return <Notice tone="warn" title="Couldn't load your notebook">{res.problem?.detail ?? "Please try again."}</Notice>;
  if (res.data.length === 0) {
    return (
      <Notice title="Nothing here yet">
        Questions you get wrong in a practice test appear here.{" "}
        <Link href="/practice" className="underline">
          Build a practice test
        </Link>
        .
      </Notice>
    );
  }
  const due = new Map<string, number>();
  for (const e of res.data) if (e.due) due.set(`${e.grade}:${e.subject}`, (due.get(`${e.grade}:${e.subject}`) ?? 0) + 1);
  return (
    <div className="space-y-6">
      {due.size > 0 && (
        <section aria-labelledby="due-h" className="space-y-2 rounded-xl border border-border bg-surface p-4">
          <h2 id="due-h" className="font-semibold">
            Due for review
          </h2>
          <ul className="space-y-2">
            {[...due.entries()].map(([key, n]) => {
              const [grade, subject] = key.split(":");
              return (
                <li key={key} className="flex flex-wrap items-center justify-between gap-3">
                  <span>
                    {GRADE_LABEL[Number(grade)]} {subject.replace("_", " ")}: {n} due
                  </span>
                  <StartReview grade={Number(grade)} subject={subject} />
                </li>
              );
            })}
          </ul>
        </section>
      )}
      <ol className="space-y-3" aria-label="Notebook entries">
        {res.data.map((e) => (
          <li key={e.id} className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
            <p className="flex flex-wrap items-center gap-2">
              <Badge tone={e.status === "mastered" ? "ok" : e.status === "voided" ? "info" : e.due ? "warn" : "info"}>
                {e.status === "open" ? (e.due ? "Due now" : "Waiting") : e.status}
              </Badge>
              <span className="text-muted">
                {GRADE_LABEL[e.grade]} {e.subject.replace("_", " ")} · missed {e.misses} time{e.misses === 1 ? "" : "s"}
              </span>
              <Link href={`/practice/attempt/${e.source_attempt_id}/result`} className="text-accent underline underline-offset-2">
                See the original question {e.position}
              </Link>
            </p>
            <LessonBlocks blocks={e.stem as { type: string }[]} headingOffset={2} />
            <p className="text-muted">{e.why}</p>
            <NoteEditor id={e.id} initial={e.note} />
          </li>
        ))}
      </ol>
    </div>
  );
}
