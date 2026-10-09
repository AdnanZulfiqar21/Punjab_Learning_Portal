"use client";

import { useRef, useState, useTransition } from "react";
import { saveNote, startReview } from "@/app/actions/practice";

export function NoteEditor({ id, initial }: { id: string; initial: string }) {
  const [note, setNote] = useState(initial);
  const [saved, setSaved] = useState(true);
  const [pending, start] = useTransition();
  return (
    <div className="flex flex-wrap items-start gap-2">
      <label className="sr-only" htmlFor={`note-${id}`}>
        Your note
      </label>
      <textarea
        id={`note-${id}`}
        value={note}
        onChange={(e) => {
          setNote(e.target.value);
          setSaved(false);
        }}
        placeholder="Your note (only you see it)"
        rows={2}
        maxLength={2000}
        className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2"
      />
      <button
        type="button"
        disabled={pending || saved}
        onClick={() =>
          start(async () => {
            const out = await saveNote(id, note);
            setSaved(out.ok);
          })
        }
        className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent disabled:opacity-60"
      >
        {saved ? "Saved" : pending ? "Saving…" : "Save note"}
      </button>
    </div>
  );
}

export function StartReview({ grade, subject }: { grade: number; subject: string }) {
  const key = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-1">
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          start(async () => {
            key.current ??= crypto.randomUUID().replaceAll("-", "");
            const out = await startReview(grade, subject, key.current);
            if (out?.error) {
              key.current = null;
              setError(out.error);
            }
          })
        }
        className="rounded-lg bg-accent px-3 py-1.5 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Preparing…" : "Review now"}
      </button>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
