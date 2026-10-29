"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { replyTicket } from "@/app/actions/support";
import { buttonClasses } from "@/components/button";
import { FIELD, LABEL, PageIcon } from "@/components/learner-pages";

export function ReplyBox({ id }: { id: string }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="glass space-y-3 rounded-card p-[22px]">
      <label htmlFor="reply" className={LABEL}>
        Add a reply
      </label>
      <textarea id="reply" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={4000} className={FIELD} />
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
        className={buttonClasses()}
      >
        <PageIcon name="send" size={16} />
        {pending ? "Sending…" : "Send reply"}
      </button>
    </div>
  );
}
