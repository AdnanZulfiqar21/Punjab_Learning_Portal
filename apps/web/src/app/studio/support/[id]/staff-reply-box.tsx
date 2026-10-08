"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { staffReply } from "@/app/actions/support";
import { STATUS_LABEL } from "@/app/help/status";

export function StaffReplyBox({ id, status }: { id: string; status: string }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [internal, setInternal] = useState(false);
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
      <label htmlFor="staff-reply" className="font-medium">
        Message to the learner or note
      </label>
      <textarea id="staff-reply" value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={4000} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
          Internal note (the learner won&apos;t see it)
        </label>
        <label htmlFor="staff-status" className="flex items-center gap-2">
          Set status
        </label>
          <select id="staff-status" value={next} onChange={(e) => setNext(e.target.value)} className="rounded-lg border border-border bg-surface px-2 py-1">
            <option value="">Keep ({STATUS_LABEL[status]})</option>
            {Object.entries(STATUS_LABEL)
              .filter(([v]) => v !== status)
              .map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
          </select>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="button"
        disabled={pending || !text.trim()}
        onClick={() =>
          start(async () => {
            const sent = text;
            const out = await staffReply(id, sent.trim(), internal, next || null);
            if (out.ok) {
              setText((t) => (t === sent ? "" : t)); // keep anything typed while this was sending
              setNext("");
              setInternal(false);
              setError(null);
              router.refresh();
            } else setError(out.error ?? null);
          })
        }
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Sending…" : internal ? "Add note" : "Send reply"}
      </button>
    </div>
  );
}
