"use client";

import { useActionState, useRef, useState } from "react";
import type { WrittenAvailability } from "@portal/contracts";
import { createWrittenPractice, type WrittenBuilderState } from "@/app/actions/written";
import { buttonClasses } from "@/components/button";
import { CHOICE_PILL, FIELD } from "@/components/practice-ui";

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
  const field = FIELD;
  return (
    <form action={action} className="space-y-7">
      <input type="hidden" name="grade" value={grade} />
      <input type="hidden" name="subject" value={subject} />
      <fieldset className="space-y-2">
        <legend className="mb-2 font-display text-lg font-semibold">Chapters</legend>
        <ul className="divide-y divide-border overflow-hidden rounded-inner border border-border bg-surface">
          {chapters.map((c) => (
            <li key={c.chapter_id}>
              <label className={`flex min-h-12 items-center gap-3 px-4 py-3 transition has-checked:bg-accent-soft ${c.questions === 0 ? "text-muted" : "cursor-pointer hover:bg-surface-muted"}`}>
                <input
                  className="size-[18px] shrink-0 accent-[var(--accent)]"
                  type="checkbox"
                  name="chapter_ids"
                  value={c.chapter_id}
                  disabled={c.questions === 0}
                  checked={selected.includes(c.chapter_id)}
                  onChange={(e) => setSelected(e.target.checked ? [...selected, c.chapter_id] : selected.filter((x) => x !== c.chapter_id))}
                />
                <span className="flex-1 font-medium">
                  Chapter {c.number}: {c.title}
                </span>
                <span className="shrink-0 rounded-full bg-[var(--track)] px-2.5 py-0.5 text-xs text-muted">{c.questions === 0 ? "none yet" : `${c.questions} written`}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <div className="flex flex-wrap items-end gap-4 rounded-inner border border-border bg-surface-muted/60 p-4">
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
        <label className={CHOICE_PILL}>
          <input className="size-4 accent-[var(--accent)]" type="checkbox" name="timed" checked={timed} onChange={(e) => setTimed(e.target.checked)} />
          Timed writing
        </label>
        {timed && (
          <label className="space-y-1">
            <span className="block font-medium">Writing minutes</span>
            <input type="number" name="writing_minutes" min={5} max={180} defaultValue={30} className={`${field} w-24`} />
          </label>
        )}
      </div>
      <div className="space-y-2 rounded-inner border border-accent/25 bg-accent-soft p-4 text-sm">
        <p className="font-display text-base font-semibold">Before you start</p>
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
        <p role="alert" className="rounded-inner border border-danger/30 bg-danger-soft px-4 py-3 text-sm">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending || selected.length === 0}
        className={buttonClasses({ size: "lg" })}
      >
        {pending ? "Preparing…" : "Start written test"}
      </button>
    </form>
  );
}
