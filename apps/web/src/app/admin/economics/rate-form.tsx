"use client";

import { useId, useState, useTransition } from "react";
import type { EconomicsReport, RateIn } from "@portal/contracts";
import { setRate, type RateResult } from "@/app/actions/economics";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";

/** Finance enters one unit rate with where it comes from; the newest rate per line is used, earlier ones are kept. */
export function RateForm({ rates }: { rates: EconomicsReport["rates"] }) {
  const id = useId();
  const [key, setKey] = useState(rates[0]?.key ?? "");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState(rates.find((r) => r.currency)?.currency ?? "");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<RateResult | null>(null);
  const [pending, start] = useTransition();
  const unit = rates.find((r) => r.key === key)?.unit ?? "";
  return (
    <form
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2"
      aria-label="Enter a rate"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          setResult(null);
          const out = await setRate({ key: key as RateIn["key"], amount, currency, source_note: note });
          setResult(out);
          if (out.ok) {
            setAmount("");
            setNote("");
          }
        });
      }}
    >
      <label className="space-y-1 text-sm" htmlFor={`${id}-key`}>
        <span className="font-medium">Cost line</span>
        <select id={`${id}-key`} value={key} onChange={(e) => setKey(e.target.value)} className={field}>
          {rates.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-[1fr_6rem] gap-2">
        <label className="space-y-1 text-sm" htmlFor={`${id}-amount`}>
          <span className="font-medium">Amount {unit && <span className="font-normal text-muted">({unit})</span>}</span>
          <input id={`${id}-amount`} inputMode="decimal" required value={amount} onChange={(e) => setAmount(e.target.value)} className={field} />
        </label>
        <label className="space-y-1 text-sm" htmlFor={`${id}-currency`}>
          <span className="font-medium">Currency</span>
          <input id={`${id}-currency`} required maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} className={field} />
        </label>
      </div>
      <label className="space-y-1 text-sm sm:col-span-2" htmlFor={`${id}-note`}>
        <span className="font-medium">Source</span>
        <span className="block text-muted">Where the figure comes from and when it was checked.</span>
        <textarea id={`${id}-note`} required minLength={10} rows={2} value={note} onChange={(e) => setNote(e.target.value)} className={field} />
      </label>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <button type="submit" disabled={pending} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
          {pending ? "Saving…" : "Save rate"}
        </button>
        {result?.ok && (
          <p role="status" className="text-sm text-ok">
            Saved. The report uses it now; earlier rates are kept.
          </p>
        )}
        {result && !result.ok && (
          <p role="alert" className="text-sm text-danger">
            {result.error}
          </p>
        )}
      </div>
    </form>
  );
}
