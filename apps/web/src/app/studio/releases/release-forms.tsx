"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { publishRelease, rollBackRelease, type ReleaseResult } from "@/app/actions/releases";

export type ApprovedItem = { id: string; title: string; detail: string; live: boolean };

function Problems({ result }: { result: ReleaseResult | null }) {
  if (!result || result.ok) return null;
  return (
    <div role="alert" className="space-y-1 text-sm text-danger">
      <p className="font-medium">{result.error}</p>
      {result.items.length > 0 && (
        <ul className="list-disc space-y-1 pl-5">
          {result.items.map((p) => (
            <li key={p.item_id}>
              {p.title || p.item_id}: {p.errors.join(" ")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// RELEASE-01: choose approved items and publish them in one step. If any item fails a check, nothing is published.
export function PublishTogether({ items }: { items: ApprovedItem[] }) {
  const router = useRouter();
  const uid = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ReleaseResult | null>(null);
  return (
    <form
      aria-label="Publish together"
      className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm"
      action={async (f) => {
        setBusy(true);
        const r = await publishRelease(
          f.getAll("item").map(String),
          String(f.get("label") ?? "").trim(),
          String(f.get("reason") ?? "").trim(),
        );
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      <fieldset className="space-y-2">
        <legend className="font-medium">Approved items</legend>
        {items.map((i) => (
          <label key={i.id} className="flex items-start gap-2">
            <input type="checkbox" name="item" value={i.id} className="mt-1" />
            <span>
              <span className="font-medium">{i.title}</span>
              <span className="block text-muted">
                {i.detail}
                {i.live ? " · replaces the version learners see now" : " · first publication"}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <label htmlFor={`${uid}-label`} className="block font-medium">
        Release name
      </label>
      <input
        id={`${uid}-label`}
        name="label"
        required
        minLength={3}
        maxLength={120}
        placeholder="For example: Chapter 4 lessons and questions"
        className="w-full rounded-lg border border-border bg-surface px-2 py-1"
      />
      <label htmlFor={`${uid}-reason`} className="block font-medium">
        Reason (recorded in the audit trail)
      </label>
      <textarea id={`${uid}-reason`} name="reason" required minLength={5} maxLength={1000} rows={2} className="w-full rounded-lg border border-border bg-surface px-2 py-1" />
      <button type="submit" disabled={busy} className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
        {busy ? "Publishing…" : "Publish together"}
      </button>
      <Problems result={result} />
    </form>
  );
}

// RELEASE-01: every item goes back to the version learners saw before, or off their screens if the release first
// published it. If any item can't go back (a newer version is live, or the earlier one fails today's checks), nothing
// changes.
export function RollBack({ id, label }: { id: string; label: string }) {
  const router = useRouter();
  const uid = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ReleaseResult | null>(null);
  return (
    <form
      aria-label={`Roll back ${label}`}
      className="space-y-2"
      action={async (f) => {
        setBusy(true);
        const r = await rollBackRelease(id, String(f.get("reason") ?? "").trim());
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      <label htmlFor={`${uid}-reason`} className="block font-medium">
        Reason for rolling back
      </label>
      <textarea id={`${uid}-reason`} name="reason" required minLength={5} maxLength={1000} rows={2} className="w-full rounded-lg border border-border bg-surface px-2 py-1" />
      <button type="submit" disabled={busy} className="rounded-lg border border-danger px-4 py-2 font-medium text-danger hover:bg-danger/10 disabled:opacity-60">
        {busy ? "Rolling back…" : "Roll back this release"}
      </button>
      <Problems result={result} />
    </form>
  );
}
