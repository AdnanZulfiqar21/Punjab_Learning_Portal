"use client";

import { useActionState, useState, useTransition } from "react";
import { publishHelp, saveHelpDraft, type HelpDraftState } from "@/app/actions/help";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2";

export function DraftForm() {
  const [state, action, pending] = useActionState<HelpDraftState, FormData>(saveHelpDraft, undefined);
  return (
    <form action={action} className="space-y-3 text-sm">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <label className="space-y-1">
          <span className="block font-medium">Slug (same slug updates that article)</span>
          <input name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" className={field} />
        </label>
        <label className="space-y-1">
          <span className="block font-medium">Language</span>
          <select name="locale" className={field}>
            <option value="en">English</option>
            <option value="ur">Urdu</option>
          </select>
        </label>
      </div>
      <label className="block space-y-1">
        <span className="block font-medium">Title</span>
        <input name="title" required maxLength={160} className={field} />
      </label>
      <label className="block space-y-1">
        <span className="block font-medium">Summary</span>
        <input name="summary" required maxLength={400} className={field} />
      </label>
      <label className="block space-y-1">
        <span className="block font-medium">Text (paragraphs; # and ## headings; - or 1. lists; &gt; notes)</span>
        <textarea name="markdown" required rows={12} className={`${field} font-mono`} />
      </label>
      <label className="block space-y-1">
        <span className="block font-medium">Tags (comma separated)</span>
        <input name="tags" className={field} />
      </label>
      {state?.error && (
        <p role="alert" className="text-danger">
          {state.error}
        </p>
      )}
      {state?.ok && <p role="status">Draft saved.</p>}
      <button type="submit" disabled={pending} className="rounded-lg border border-border px-4 py-2 font-medium disabled:opacity-60">
        {pending ? "Saving…" : "Save draft"}
      </button>
    </form>
  );
}

export function PublishButton({ id, action }: { id: string; action: "publish" | "retire" }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          start(async () => {
            const out = await publishHelp(id, action);
            setError(out.error ?? null);
          })
        }
        className="rounded-lg border border-border px-3 py-1.5 font-medium disabled:opacity-60"
      >
        {action === "publish" ? "Publish" : "Retire"}
      </button>
      {error && (
        <span role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
    </span>
  );
}
