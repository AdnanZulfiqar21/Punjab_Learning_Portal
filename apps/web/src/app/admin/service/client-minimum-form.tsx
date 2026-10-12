"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { setClientMinimum, type RolloutResult } from "@/app/actions/operations";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const button = "rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

/** P13.S1.T4 (CLIENTS-01): raise (with 14 days' notice, outside mock windows) or lower a platform's minimum version. */
export function ClientMinimumForm({ platform, label }: { platform: string; label: string }) {
  const router = useRouter();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RolloutResult | null>(null);
  return (
    <form
      aria-label={`Set the minimum ${label} app version`}
      className="grid gap-3 text-sm sm:grid-cols-[8rem_12rem_1fr_auto] sm:items-end"
      action={async (f) => {
        setBusy(true);
        const r = await setClientMinimum(platform, f);
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      <div className="space-y-1">
        <label htmlFor={`${id}-v`} className="block font-medium">
          Minimum version
        </label>
        <input id={`${id}-v`} name="min_version" required pattern="[0-9]+\.[0-9]+\.[0-9]+" placeholder="1.4.0" className={field} />
      </div>
      <div className="space-y-1">
        <label htmlFor={`${id}-w`} className="block font-medium">
          Takes effect (blank = in 14 days)
        </label>
        <input id={`${id}-w`} name="enforce_at" type="datetime-local" className={field} />
      </div>
      <div className="space-y-1">
        <label htmlFor={`${id}-r`} className="block font-medium">
          Reason (recorded in the audit trail)
        </label>
        <input id={`${id}-r`} name="reason" required minLength={10} maxLength={1000} className={field} />
      </div>
      <button type="submit" disabled={busy} className={button}>
        {busy ? "Saving…" : "Set minimum"}
      </button>
      {result && (
        <p role={result.ok ? "status" : "alert"} className={`sm:col-span-4 ${result.ok ? "text-muted" : "text-danger"}`}>
          {result.ok ? "Saved. Apps below this version are told the date now and stop working then." : result.error}
        </p>
      )}
    </form>
  );
}
