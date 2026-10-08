"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import type { WrittenResult } from "@portal/contracts";
import { prepareLinkedPractice } from "@/app/actions/written";

const date = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const REASON: Record<string, string> = {
  REWRITE: "rewrite after feedback",
  NEW_CONTENT: "new work from a clearer copy",
  INDETERMINATE: "new practice after an unclear copy",
};
const STATUS: Record<string, string> = { not_started: "not started", active: "in progress", sealed: "submitted", expired: "expired" };

// W04.S3.T3: answering again is a separate, linked practice test with its own allowance use. It never changes the
// result above; to have the same answer looked at again, the learner asks for a recheck instead.
export function PractiseAgain({ attemptId, result }: { attemptId: string; result: WrittenResult }) {
  const [picked, setPicked] = useState<number[]>(result.questions.map((q) => q.position));
  const [key] = useState(() => crypto.randomUUID());
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const linked = result.linked_attempts ?? [];
  return (
    <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
      <h3 className="font-semibold">Practise these questions again</h3>
      <p className="text-sm text-muted">
        Write fresh answers as a new practice test. It is marked on its own and uses your written allowance like any test (you&apos;ll see how much
        before it starts). The marks above stay as they are; if you think a teacher misread this script, a recheck is the right route.
      </p>
      <fieldset className="flex flex-wrap gap-3 text-sm">
        <legend className="sr-only">Questions to practise again</legend>
        {result.questions.map((q) => (
          <label key={q.position} className="inline-flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={picked.includes(q.position)}
              onChange={(e) => setPicked((p) => (e.target.checked ? [...p, q.position].sort((a, b) => a - b) : p.filter((x) => x !== q.position)))}
            />
            Question {q.position}
          </label>
        ))}
      </fieldset>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="button"
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
        disabled={pending || picked.length === 0}
        onClick={() =>
          start(async () => {
            setError(null);
            const out = await prepareLinkedPractice(attemptId, key, "REWRITE", picked, null);
            if (out?.error) setError(out.error);
          })
        }
      >
        {pending ? "Preparing…" : "Prepare a new practice test"}
      </button>
      {linked.length > 0 && (
        <div className="text-sm">
          <p className="font-semibold">Linked practice tests</p>
          <ul>
            {linked.map((l) => (
              <li key={l.form_id}>
                <Link className="text-accent underline" href={l.attempt_id ? `/practice/written/${l.attempt_id}` : `/practice/written/linked/${l.form_id}`}>
                  Questions {l.positions.join(", ")}
                </Link>{" "}
                · {REASON[l.reason]} · {STATUS[l.status]} · {date(l.created_at)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
