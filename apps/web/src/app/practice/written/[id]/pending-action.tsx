"use client";

// What a learner can do about a pending question within the teacher's 7-day window (W06.S2.T4): send a clearer copy
// of the same answer, or (for blank-looking evidence) confirm it wasn't answered. Neither replaces the sealed original.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { WrittenResult } from "@portal/contracts";
import { confirmUnanswered } from "@/app/actions/written";

type Question = WrittenResult["questions"][number];
const when = (s: string) => new Date(s).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const CLASS_TEXT: Record<string, string> = {
  READABILITY: "A teacher used your clearer copy to mark this answer.",
  NEW_CONTENT: "Your copy showed new or changed work, so the original result stands. You can start a new practice test to have new work marked.",
  INDETERMINATE: "The original was too unclear to compare with your copy.",
};

export function PendingAction({ attemptId, q }: { attemptId: string; q: Question }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [busy, setBusy] = useState(false);
  const open = q.status === "pending" && q.learner_action && q.action_deadline && new Date(q.action_deadline) > new Date();

  async function send(file: File) {
    setBusy(true);
    setError(null);
    const res = await fetch(`/practice/written/${attemptId}/questions/${q.position}/rescan?note=${encodeURIComponent("Clearer copy")}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    setBusy(false);
    if (res.ok) router.refresh();
    else setError(((await res.json().catch(() => null)) as { detail?: string } | null)?.detail ?? "That didn't upload.");
  }

  return (
    <div className="space-y-2 text-sm">
      {(q.revisions ?? []).map((r) => (
        <p key={r.id} className="rounded bg-surface-muted px-2 py-1">
          Clearer copy sent {when(r.created_at)}: {r.classification ? CLASS_TEXT[r.classification] : "waiting for a teacher to compare it with your original."}
          {r.classification === "NEW_CONTENT" && (
            <>
              {" "}
              <Link href="/practice/written" className="text-accent underline">
                Start a new practice test
              </Link>
            </>
          )}
        </p>
      ))}
      {open && (
        <div className="space-y-2 rounded-lg border border-warn bg-warn-soft p-3" role="group" aria-label={`Action for question ${q.position}`}>
          <p>
            {q.learner_action === "confirm_or_rescan"
              ? "This answer looks blank to the teacher. Send a clearer photo of it, or tell us you didn't answer it."
              : "The teacher couldn't read this answer. Send a clearer photo of the same page (not a new answer)."}{" "}
            Please act by {when(q.action_deadline!)}; after that the question is left unmarked and its allowance returned.
          </p>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 font-medium">
            <input type="file" accept="image/jpeg,image/png,application/pdf" className="sr-only" disabled={busy} onChange={(e) => e.target.files?.[0] && void send(e.target.files[0])} />
            {busy ? "Sending…" : "Send a clearer copy"}
          </label>
          {q.learner_action === "confirm_or_rescan" && (
            <button
              type="button"
              disabled={pending}
              onClick={() =>
                start(async () => {
                  const out = await confirmUnanswered(attemptId, q.position);
                  if (out.ok) router.refresh();
                  else setError(out.error ?? null);
                })
              }
              className="ml-2 rounded-lg border border-border bg-surface px-3 py-1.5 font-medium"
            >
              I didn&apos;t answer this question
            </button>
          )}
          {error && (
            <p role="alert" className="text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
