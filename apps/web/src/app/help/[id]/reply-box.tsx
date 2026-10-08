"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { replyTicket } from "@/app/actions/support";

export function ReplyBox({ id }: { id: string }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-2">
      <label htmlFor="reply" className="font-medium">
        Add a reply
      </label>
      <textarea id="reply" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={4000} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
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
            const out = await replyTicket(id, sent.trim());
            if (out.ok) {
              setText((t) => (t === sent ? "" : t)); // keep anything typed while this was sending
              router.refresh();
            } else setError(out.error ?? null);
          })
        }
        className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent disabled:opacity-60"
      >
        {pending ? "Sending…" : "Send reply"}
      </button>
    </div>
  );
}
