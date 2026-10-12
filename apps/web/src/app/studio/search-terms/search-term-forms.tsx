"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { approveTerms, proposeTerms, retireTerms, type SearchTermResult } from "@/app/actions/search-terms";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const button = "rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";
const small = "rounded-lg border border-border bg-surface px-3 py-1 text-sm hover:border-accent disabled:opacity-60";

export function ProposeTerms({ grade, subject }: { grade: string; subject: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SearchTermResult | null>(null);
  return (
    <form
      aria-label="Propose search terms"
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 text-sm sm:grid-cols-3"
      action={async (f) => {
        setBusy(true);
        const r = await proposeTerms(f);
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      <input type="hidden" name="grade" value={grade} />
      <input type="hidden" name="subject" value={subject} />
      <label className="space-y-1">
        <span className="block font-medium">English</span>
        <textarea name="en" rows={2} maxLength={400} className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Urdu</span>
        <textarea name="ur" rows={2} maxLength={400} lang="ur" dir="rtl" className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Roman Urdu spellings</span>
        <textarea name="roman_ur" rows={2} maxLength={400} className={field} />
      </label>
      <p className="text-muted sm:col-span-3">One form per line. Only terms that appear in the owner&apos;s material, as written there.</p>
      <label className="space-y-1 sm:col-span-3">
        <span className="block font-medium">Where they come from (document and page)</span>
        <input name="source_ref" required minLength={3} maxLength={300} className={field} />
      </label>
      <div className="sm:col-span-3">
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Proposing…" : "Propose for review"}
        </button>
        {result && !result.ok && (
          <p role="alert" className="text-danger">
            {result.error}
          </p>
        )}
      </div>
    </form>
  );
}

export function TermActions({ id, canApprove, canRetire }: { id: string; canApprove: boolean; canRetire: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const run = async (act: () => Promise<SearchTermResult>) => {
    setBusy(true);
    const r = await act();
    setBusy(false);
    if (r.ok) router.refresh();
    else setError(r.error);
  };
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      {canApprove && (
        <button type="button" disabled={busy} className={small} onClick={() => run(() => approveTerms(id))}>
          Approve
        </button>
      )}
      {canRetire && (
        <>
          <input
            aria-label="Reason for retiring"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={300}
            placeholder="Reason"
            className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
          />
          <button type="button" disabled={busy || reason.trim().length < 3} className={small} onClick={() => run(() => retireTerms(id, reason.trim()))}>
            Retire
          </button>
        </>
      )}
      {error && (
        <span role="alert" className="text-danger">
          {error}
        </span>
      )}
    </span>
  );
}
