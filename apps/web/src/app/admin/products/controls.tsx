"use client";

import { useId, useState, useTransition } from "react";
import { addPrice, createProduct, moveProduct, type ProductResult } from "@/app/actions/products";
import { formatMinor, toMinor } from "@/lib/money";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const btn = "rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent disabled:opacity-60";
const KINDS: [string, string][] = [
  ["subject_package", "Subject package"],
  ["exam_package", "Exam package"],
  ["bundle", "Bundle"],
  ["platform", "Whole platform"],
];

function useAction() {
  const [result, setResult] = useState<ProductResult | null>(null);
  const [pending, start] = useTransition();
  const run = (fn: () => Promise<ProductResult>, onOk?: () => void) =>
    start(async () => {
      setResult(null);
      const out = await fn();
      setResult(out);
      if (out.ok) onOk?.();
    });
  const alert =
    result && !result.ok ? (
      <p role="alert" className="text-sm text-danger">
        {result.error}
      </p>
    ) : null;
  return { pending, run, alert };
}

export function NewProduct({ subjects }: { subjects: { code: string; name: string }[] }) {
  const id = useId();
  const [v, setV] = useState({ code: "", name: "", kind: "subject_package", days: "180", units: "0", description: "", exams: "" });
  const [grades, setGrades] = useState<number[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const { pending, run, alert } = useAction();
  const toggle = <T,>(list: T[], x: T) => (list.includes(x) ? list.filter((y) => y !== x) : [...list, x]);
  const submit = () =>
    run(
      () =>
        createProduct({
          code: v.code.trim(),
          name: v.name.trim(),
          kind: v.kind as "subject_package" | "exam_package" | "bundle" | "platform",
          scope: {
            grades,
            subjects: picked,
            exams: v.exams
              .split(",")
              .map((e) => e.trim())
              .filter(Boolean),
          },
          duration_days: Number(v.days),
          written_units: Number(v.units),
          description: v.description.trim(),
        }),
      () => {
        setV({ code: "", name: "", kind: "subject_package", days: "180", units: "0", description: "", exams: "" });
        setGrades([]);
        setPicked([]);
      },
    );
  return (
    <form
      aria-label="New product"
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 text-sm sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <h2 className="font-semibold sm:col-span-2">New product (draft)</h2>
      <label className="space-y-1">
        <span className="block font-medium">Code</span>
        <input required value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} placeholder="e.g. bio-11-12" className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Name</span>
        <input required minLength={3} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Kind</span>
        <select value={v.kind} onChange={(e) => setV({ ...v, kind: e.target.value })} className={field}>
          {KINDS.map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <fieldset className="space-y-1">
        <legend className="font-medium">Classes</legend>
        <div className="flex gap-4">
          {[11, 12].map((g) => (
            <label key={g} className="flex items-center gap-2">
              <input type="checkbox" checked={grades.includes(g)} onChange={() => setGrades(toggle(grades, g))} />
              Class {g === 11 ? "XI" : "XII"}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-1 sm:col-span-2">
        <legend className="font-medium">Subjects</legend>
        <div className="flex flex-wrap gap-4">
          {subjects.map((s) => (
            <label key={s.code} className="flex items-center gap-2">
              <input type="checkbox" checked={picked.includes(s.code)} onChange={() => setPicked(toggle(picked, s.code))} />
              {s.name}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="space-y-1">
        <span className="block font-medium">Exam profile codes</span>
        <input value={v.exams} onChange={(e) => setV({ ...v, exams: e.target.value })} placeholder="Comma-separated, e.g. MDCAT" className={field} aria-describedby={`${id}-exams`} />
        <span id={`${id}-exams`} className="block text-xs text-muted">
          Only for exam packages and bundles.
        </span>
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Valid for (days)</span>
        <input type="number" min={1} max={366} required value={v.days} onChange={(e) => setV({ ...v, days: e.target.value })} className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Written answers included</span>
        <input type="number" min={0} max={500} required value={v.units} onChange={(e) => setV({ ...v, units: e.target.value })} className={field} />
      </label>
      <label className="space-y-1 sm:col-span-2">
        <span className="block font-medium">Description (shown to learners)</span>
        <textarea rows={2} maxLength={2000} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} className={field} />
      </label>
      <div className="sm:col-span-2">
        <button type="submit" disabled={pending} className={btn}>
          {pending ? "Saving…" : "Save draft product"}
        </button>
        {alert}
      </div>
    </form>
  );
}

export function MoveProduct({ id, to, label }: { id: string; to: "activate" | "retire"; label: string }) {
  const [reason, setReason] = useState("");
  const { pending, run, alert } = useAction();
  return (
    <form
      aria-label={label}
      className="flex flex-wrap items-end gap-2 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        run(() => moveProduct(id, to, reason.trim()), () => setReason(""));
      }}
    >
      <label className="min-w-56 flex-1 space-y-1">
        <span className="block font-medium">{to === "retire" ? "Why retire it" : "Why put it on sale"} (recorded in the audit trail)</span>
        <input required minLength={10} value={reason} onChange={(e) => setReason(e.target.value)} className={field} />
      </label>
      <button type="submit" disabled={pending} className={btn}>
        {label}
      </button>
      {alert}
    </form>
  );
}

export function AddPrice({ id, name }: { id: string; name: string }) {
  const [v, setV] = useState({ currency: "PKR", amount: "", starts: "", reason: "", onSale: true });
  const { pending, run, alert } = useAction();
  const minor = v.onSale ? toMinor(v.amount, v.currency) : null;
  return (
    <form
      aria-label={`Add a price for ${name}`}
      className="grid gap-2 text-sm sm:grid-cols-4"
      onSubmit={(e) => {
        e.preventDefault();
        run(
          () =>
            addPrice(id, {
              currency: v.currency,
              amount_minor: minor,
              on_sale: v.onSale,
              starts_at: v.starts ? new Date(v.starts).toISOString() : null,
              reason: v.reason.trim(),
            }),
          () => setV({ ...v, amount: "", starts: "", reason: "" }),
        );
      }}
    >
      <label className="space-y-1">
        <span className="block font-medium">Currency</span>
        <input required pattern="[A-Z]{3}" maxLength={3} value={v.currency} onChange={(e) => setV({ ...v, currency: e.target.value.toUpperCase() })} className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Amount</span>
        <input inputMode="decimal" disabled={!v.onSale} required={v.onSale} value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} className={field} />
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Starts (blank = now)</span>
        <input type="datetime-local" value={v.starts} onChange={(e) => setV({ ...v, starts: e.target.value })} className={field} />
      </label>
      <label className="flex items-center gap-2 self-end pb-2">
        <input type="checkbox" checked={v.onSale} onChange={(e) => setV({ ...v, onSale: e.target.checked })} />
        On sale
      </label>
      <label className="space-y-1 sm:col-span-3">
        <span className="block font-medium">Why this price (recorded in the audit trail)</span>
        <input required minLength={10} value={v.reason} onChange={(e) => setV({ ...v, reason: e.target.value })} className={field} />
      </label>
      <div className="self-end">
        <button type="submit" disabled={pending || (v.onSale && minor === null)} className={btn}>
          Add price version
        </button>
      </div>
      {v.onSale && v.amount && minor === null && (
        <p role="alert" className="text-danger sm:col-span-4">
          Enter an amount like 2500 or 2500.50.
        </p>
      )}
      {minor !== null && <p className="text-muted sm:col-span-4">Will be stored as {formatMinor(minor, v.currency)} ({minor} minor units).</p>}
      <div className="sm:col-span-4">{alert}</div>
    </form>
  );
}
