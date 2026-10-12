"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import type { StudioItemSummary } from "@portal/contracts";
import { createQuestionVariant } from "@/app/actions/studio";
import { Badge } from "@/components/ui";

const STATE: Record<string, string> = {
  draft: "Draft",
  submitted: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  published: "Published",
};

type Question = { id: string; kind: "mcq" | "written"; chapterId: string; topicId: string | null; title: string };

/** P08.S3.T2: a question's variants (one family), each with its own state, and starting another one. */
export function QuestionVariants({ item, family, canAdd }: { item: Question; family: StudioItemSummary[]; canAdd: boolean }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <section aria-labelledby="question-variants-h" className="space-y-2 rounded-xl border border-border bg-surface px-4 py-3 text-sm">
      <h2 id="question-variants-h" className="font-semibold">
        Question variants
      </h2>
      <p className="text-muted">
        A variant tests the same skill in another way. It has its own key, explanation and review, and never changes this question. Mistake review prefers
        a different variant from the same family, and progress evidence limits how much one family counts.
      </p>
      <ul className="space-y-1">
        {family.map((v) => (
          <li key={v.id} className="flex flex-wrap items-center gap-2">
            <Badge tone={v.state === "published" && v.availability === "live" ? "ok" : "info"}>{STATE[v.state] ?? v.state}</Badge>
            {v.id === item.id ? (
              <span className="font-medium">{v.title} (this question)</span>
            ) : (
              <Link href={`/studio/items/${v.id}`} className="text-accent underline-offset-2 hover:underline">
                {v.title}
              </Link>
            )}
            {v.availability !== "live" && v.availability !== "unpublished" && <span className="text-muted">{v.availability}</span>}
          </li>
        ))}
      </ul>
      {canAdd && (
        <div className="space-y-1">
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              start(async () => {
                setError(null);
                const r = await createQuestionVariant(item.id, item.kind, item.chapterId, item.topicId, item.title);
                if (r?.error) setError(r.error);
              })
            }
            className="rounded-lg border border-border px-3 py-1.5 font-medium hover:border-accent disabled:opacity-60"
          >
            {pending ? "Starting…" : "Make a variant"}
          </button>
          {error && (
            <p role="alert" className="text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
