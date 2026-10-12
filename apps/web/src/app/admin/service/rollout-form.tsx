"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { setRollout, type RolloutResult } from "@/app/actions/operations";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const button = "rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

export function RolloutForm({ rolloutKey, label, percent }: { rolloutKey: string; label: string; percent: number }) {
  const router = useRouter();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RolloutResult | null>(null);
  return (
    <form
      aria-label={`Change the rollout of ${label}`}
      className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr_auto] sm:items-end"
      action={async (f) => {
        setBusy(true);
        const r = await setRollout(rolloutKey, f);
        setBusy(false);
        setResult(r);
        if (r.ok) router.refresh();
      }}
    >
      <div className="space-y-1">
        <label htmlFor={`${id}-percent`} className="block font-medium">
          Learners (%)
        </label>
        <input id={`${id}-percent`} name="percent" type="number" min={0} max={100} step={1} required defaultValue={percent} className={field} />
      </div>
      <div className="space-y-1">
        <label htmlFor={`${id}-reason`} className="block font-medium">
          Reason (recorded in the audit trail)
        </label>
        <input id={`${id}-reason`} name="reason" required minLength={10} maxLength={1000} className={field} />
      </div>
      <button type="submit" disabled={busy} className={button}>
        {busy ? "Saving…" : "Save rollout"}
      </button>
      {result && (
        <p role={result.ok ? "status" : "alert"} className={`sm:col-span-3 ${result.ok ? "text-muted" : "text-danger"}`}>
          {result.ok ? "Saved. Learners see the change on their next page." : result.error}
        </p>
      )}
    </form>
  );
}
