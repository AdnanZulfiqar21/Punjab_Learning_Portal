"use client";

import { useActionState, useRef, useState } from "react";
import type { PracticeAvailability } from "@portal/contracts";
import { createPractice, type BuilderState } from "@/app/actions/practice";

const newKey = () => crypto.randomUUID().replaceAll("-", "");

export function PracticeBuilder({ grade, subject, chapters }: { grade: number; subject: string; chapters: PracticeAvailability["chapters"] }) {
  // One idempotency key per test request: a double click or a retry returns the same test; a changed request gets a
  // fresh key after an error so it is never mistaken for the earlier one.
  const key = useRef<string | null>(null);
  const [state, action, pending] = useActionState<BuilderState, FormData>(async (prev, form) => {
    key.current ??= newKey();
    form.set("idempotency_key", key.current);
    const out = await createPractice(prev, form);
    if (out?.error) key.current = null;
    return out;
  }, undefined);
  const [selected, setSelected] = useState<string[]>([]);
  const [timed, setTimed] = useState(false);
  const available = chapters.filter((c) => selected.includes(c.chapter_id)).reduce((n, c) => n + c.questions, 0);
  const field = "rounded-lg border border-border bg-surface px-3 py-2";

  return (
    <form action={action} className="space-y-6">
      <input type="hidden" name="grade" value={grade} />
      <input type="hidden" name="subject" value={subject} />
      <fieldset className="space-y-2">
        <legend className="font-medium">Chapters</legend>
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
          {chapters.map((c) => (
            <li key={c.chapter_id}>
              <label className={`flex items-center gap-3 px-4 py-3 ${c.questions === 0 ? "text-muted" : ""}`}>
                <input
                  type="checkbox"
                  name="chapter_ids"
                  value={c.chapter_id}
                  disabled={c.questions === 0}
                  checked={selected.includes(c.chapter_id)}
                  onChange={(e) => setSelected(e.target.checked ? [...selected, c.chapter_id] : selected.filter((x) => x !== c.chapter_id))}
                />
                <span className="flex-1">
                  Chapter {c.number}: {c.title}
                </span>
                <span className="text-sm text-muted">{c.questions === 0 ? "no questions yet" : `${c.questions} questions`}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <div className="flex flex-wrap items-end gap-4">
        <label className="space-y-1">
          <span className="block font-medium">Questions</span>
          <input type="number" name="question_count" min={1} max={Math.max(1, Math.min(100, available))} defaultValue={Math.min(10, Math.max(1, available))} className={`${field} w-28`} />
        </label>
        <label className="space-y-1">
          <span className="block font-medium">Feedback</span>
          <select name="feedback_mode" defaultValue="deferred" className={field}>
            <option value="deferred">After I submit</option>
            <option value="immediate">After each question</option>
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2">
          <input type="checkbox" name="timed" checked={timed} onChange={(e) => setTimed(e.target.checked)} />
          Timed
        </label>
        {timed && (
          <label className="space-y-1">
            <span className="block font-medium">Minutes</span>
            <input type="number" name="timed_minutes" min={1} max={300} defaultValue={15} className={`${field} w-24`} />
          </label>
        )}
      </div>
      {timed && (
        <p className="text-sm text-muted">
          Timed practice closes editing at the deadline. Answers that haven&apos;t reached the server within 3 seconds after it can be
          rejected, so keep your connection steady near the end.
        </p>
      )}
      {selected.length > 0 && <p className="text-sm text-muted">{available} approved questions available in the chosen chapters.</p>}
      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
          {state.available !== undefined ? ` You can ask for up to ${state.available}.` : ""}
        </p>
      )}
      <button
        type="submit"
        disabled={pending || selected.length === 0}
        className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Preparing…" : "Start test"}
      </button>
    </form>
  );
}
