"use client";

import { useActionState, useRef, useState } from "react";
import type { WrittenAvailability } from "@portal/contracts";
import { createWrittenPractice, type WrittenBuilderState } from "@/app/actions/written";

const newKey = () => crypto.randomUUID().replaceAll("-", "");

export function WrittenBuilder({
  grade,
  subject,
  chapters,
  uploadAllowanceS,
  caps,
}: {
  grade: number;
  subject: string;
  chapters: WrittenAvailability["chapters"];
  uploadAllowanceS: number;
  caps: Record<string, number>;
}) {
  const key = useRef<string | null>(null);
  const [state, action, pending] = useActionState<WrittenBuilderState, FormData>(async (prev, form) => {
    key.current ??= newKey();
    form.set("idempotency_key", key.current);
    const out = await createWrittenPractice(prev, form);
    if (out?.error) key.current = null;
    return out;
  }, undefined);
  const [selected, setSelected] = useState<string[]>([]);
  const [timed, setTimed] = useState(true);
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
                <span className="text-sm text-muted">{c.questions === 0 ? "none yet" : `${c.questions} written`}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <div className="flex flex-wrap items-end gap-4">
        <label className="space-y-1">
          <span className="block font-medium">Questions</span>
          <input type="number" name="question_count" min={1} max={10} defaultValue={1} className={`${field} w-24`} />
        </label>
        <label className="space-y-1">
          <span className="block font-medium">Question type</span>
          <select name="question_type" defaultValue="mixed" className={field}>
            <option value="mixed">Short and long</option>
            <option value="short">Short only</option>
            <option value="long">Long only</option>
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2">
          <input type="checkbox" name="timed" checked={timed} onChange={(e) => setTimed(e.target.checked)} />
          Timed writing
        </label>
        {timed && (
          <label className="space-y-1">
            <span className="block font-medium">Writing minutes</span>
            <input type="number" name="writing_minutes" min={5} max={180} defaultValue={30} className={`${field} w-24`} />
          </label>
        )}
      </div>
      <div className="space-y-1 rounded-xl border border-border bg-surface-muted p-4 text-sm">
        <p className="font-medium">Before you start</p>
        <ul className="list-disc space-y-1 pl-5">
          {timed ? (
            <li>
              Writing time ends at the deadline. You then have {Math.round(uploadAllowanceS / 60)} more minutes to photograph, upload and submit
              your pages. Nothing is accepted after that.
            </li>
          ) : (
            <li>Untimed: upload and submit within {Math.round(uploadAllowanceS / 3600)} hours of starting.</li>
          )}
          <li>
            Up to {caps.max_pages} files, {Math.round(caps.max_total_bytes / 1048576)} MB in total (JPEG or PNG photos, or a PDF). Uploads can be slow on mobile
            data; start uploading as soon as your pages are ready.
          </li>
          <li>We can&apos;t check when you actually stopped writing at home, so the deadline is on trust.</li>
          <li>A teacher marks your answers against the approved rubric. Pages you upload but don&apos;t submit are not marked.</li>
        </ul>
      </div>
      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending || selected.length === 0}
        className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Preparing…" : "Start written test"}
      </button>
    </form>
  );
}
