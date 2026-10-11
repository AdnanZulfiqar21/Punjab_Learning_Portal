"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { draftRecord, publishRecord, type InclusionResult } from "@/app/actions/inclusion";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const button = "rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

export function DraftRecord({ concepts, scope, year }: { concepts: { id: string; label: string }[]; scope: string; year: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<InclusionResult | null>(null);
  return (
    <form
      aria-label="Draft an inclusion record"
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 text-sm sm:grid-cols-2"
      action={async (f) => {
        setBusy(true);
        const r = await draftRecord(f);
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      <input type="hidden" name="scope" value={scope} />
      <input type="hidden" name="year" value={year} />
      <label className="space-y-1 sm:col-span-2">
        <span className="block font-medium">Concept</span>
        <select name="concept_id" required className={field}>
          {concepts.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1">
        <span className="block font-medium">State</span>
        <select name="state" className={field}>
          <option value="included">Included</option>
          <option value="excluded">Excluded</option>
          <option value="not_applicable">Not applicable</option>
          <option value="unverified">Unverified</option>
        </select>
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Source version</span>
        <input name="source_version" required maxLength={120} placeholder="e.g. notice dated 2026-06-01" className={field} />
      </label>
      <label className="space-y-1 sm:col-span-2">
        <span className="block font-medium">Source (document, section or page)</span>
        <input name="source" required minLength={3} maxLength={500} className={field} />
      </label>
      <label className="space-y-1 sm:col-span-2">
        <span className="block font-medium">Reason</span>
        <textarea name="reason" required minLength={3} maxLength={2000} rows={2} className={field} />
      </label>
      <div className="sm:col-span-2">
        <button type="submit" disabled={busy || concepts.length === 0} className={button}>
          {busy ? "Saving…" : "Save draft record"}
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

export function PublishRecord({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        disabled={busy}
        className="rounded-lg border border-border bg-surface px-3 py-1 text-sm hover:border-accent disabled:opacity-60"
        onClick={async () => {
          setBusy(true);
          const r = await publishRecord(id);
          setBusy(false);
          if (r.ok) router.refresh();
          else setError(r.error);
        }}
      >
        {busy ? "Publishing…" : "Approve and publish"}
      </button>
      {error && (
        <span role="alert" className="text-danger">
          {error}
        </span>
      )}
    </span>
  );
}
