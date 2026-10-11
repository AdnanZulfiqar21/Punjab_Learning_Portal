"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  addPrerequisite,
  createConcept,
  mapTopics,
  publishConcept,
  removePrerequisite,
  updateConcept,
  type ConceptResult,
} from "@/app/actions/concepts";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const button = "rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";
const secondary = "rounded-lg border border-border bg-surface px-3 py-1.5 text-sm hover:border-accent disabled:opacity-60";

function useRun() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ConceptResult | null>(null);
  async function run(fn: () => Promise<ConceptResult>, then?: (r: ConceptResult) => void) {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    setResult(r);
    if (r.ok) {
      then?.(r);
      router.refresh();
    }
  }
  return { busy, result, run };
}

function Problems({ result }: { result: ConceptResult | null }) {
  if (!result || result.ok) return null;
  return (
    <div role="alert" className="text-sm text-danger">
      <p>{result.error}</p>
      {result.errors && (
        <ul className="list-disc pl-5">
          {result.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NewConcept({ subjects }: { subjects: [string, string][] }) {
  const router = useRouter();
  const { busy, result, run } = useRun();
  return (
    <form
      action={(f) => run(() => createConcept(f), (r) => r.ok && r.id && router.push(`/studio/concepts/${r.id}`))}
      className="grid gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-2"
      aria-label="New concept"
    >
      <label className="space-y-1 text-sm">
        <span className="block font-medium">Code</span>
        <input name="code" required pattern="[a-z0-9][a-z0-9.\-]{2,79}" placeholder="bio.cell.membrane-transport" className={`${field} font-mono`} />
        <span className="block text-xs text-muted">Stable identifier: lower-case letters, digits, dots and hyphens.</span>
      </label>
      <label className="space-y-1 text-sm">
        <span className="block font-medium">Subject</span>
        <select name="subject" className={field}>
          {subjects.map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1 text-sm sm:col-span-2">
        <span className="block font-medium">Title</span>
        <input name="title" required maxLength={200} className={field} />
      </label>
      <label className="space-y-1 text-sm sm:col-span-2">
        <span className="block font-medium">Learning outcome</span>
        <textarea name="statement" required maxLength={2000} rows={3} className={field} />
      </label>
      <div className="sm:col-span-2">
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Saving…" : "Save draft concept"}
        </button>
        <Problems result={result} />
      </div>
    </form>
  );
}

export function EditConcept({
  id,
  title,
  statement,
  refs,
  sources,
}: {
  id: string;
  title: string;
  statement: string;
  refs: { source_document_id: string; pdf_from: number; pdf_to: number }[];
  sources: { id: string; label: string }[];
}) {
  const { busy, result, run } = useRun();
  const [t, setT] = useState(title);
  const [s, setS] = useState(statement);
  const [r, setR] = useState(refs.length ? refs : [{ source_document_id: sources[0]?.id ?? "", pdf_from: 1, pdf_to: 1 }]);
  return (
    <div className="space-y-3 text-sm">
      <label className="block space-y-1">
        <span className="block font-medium">Title</span>
        <input value={t} onChange={(e) => setT(e.target.value)} maxLength={200} className={field} />
      </label>
      <label className="block space-y-1">
        <span className="block font-medium">Learning outcome</span>
        <textarea value={s} onChange={(e) => setS(e.target.value)} maxLength={2000} rows={3} className={field} />
      </label>
      <fieldset className="space-y-2">
        <legend className="font-medium">Source pages (textbook PDF)</legend>
        {r.map((ref, i) => (
          <div key={i} className="flex flex-wrap items-end gap-2">
            <select
              aria-label={`Source ${i + 1}`}
              value={ref.source_document_id}
              onChange={(e) => setR(r.map((x, j) => (j === i ? { ...x, source_document_id: e.target.value } : x)))}
              className="rounded-lg border border-border bg-surface px-2 py-2"
            >
              {sources.map((src) => (
                <option key={src.id} value={src.id}>
                  {src.label}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              aria-label={`Source ${i + 1} first PDF page`}
              value={ref.pdf_from}
              onChange={(e) => setR(r.map((x, j) => (j === i ? { ...x, pdf_from: Number(e.target.value) } : x)))}
              className="w-24 rounded-lg border border-border bg-surface px-2 py-2"
            />
            <input
              type="number"
              min={1}
              aria-label={`Source ${i + 1} last PDF page`}
              value={ref.pdf_to}
              onChange={(e) => setR(r.map((x, j) => (j === i ? { ...x, pdf_to: Number(e.target.value) } : x)))}
              className="w-24 rounded-lg border border-border bg-surface px-2 py-2"
            />
          </div>
        ))}
        <button type="button" className={secondary} onClick={() => setR([...r, { source_document_id: sources[0]?.id ?? "", pdf_from: 1, pdf_to: 1 }])}>
          Add another source range
        </button>
      </fieldset>
      <button type="button" disabled={busy} className={button} onClick={() => run(() => updateConcept(id, { title: t, statement: s, source_refs: r.filter((x) => x.source_document_id) }))}>
        {busy ? "Saving…" : "Save concept"}
      </button>
      <Problems result={result} />
    </div>
  );
}

export function TopicPicker({ id, mapped, chapterTopics }: { id: string; mapped: string[]; chapterTopics: { id: string; label: string }[] }) {
  const { busy, result, run } = useRun();
  const [chosen, setChosen] = useState<Set<string>>(new Set(mapped));
  return (
    <div className="space-y-2 text-sm">
      <ul className="max-h-80 space-y-1 overflow-y-auto rounded-lg border border-border bg-surface p-2">
        {chapterTopics.map((t) => (
          <li key={t.id}>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={chosen.has(t.id)}
                onChange={(e) => {
                  const next = new Set(chosen);
                  if (e.target.checked) next.add(t.id);
                  else next.delete(t.id);
                  setChosen(next);
                }}
              />
              <span>{t.label}</span>
            </label>
          </li>
        ))}
      </ul>
      <button type="button" disabled={busy} className={button} onClick={() => run(() => mapTopics(id, [...chosen]))}>
        {busy ? "Saving…" : "Save topic mapping"}
      </button>
      <Problems result={result} />
    </div>
  );
}

export function Prerequisites({
  id,
  current,
  options,
  editable,
}: {
  id: string;
  current: { id: string; label: string }[];
  options: { id: string; label: string }[];
  editable: boolean;
}) {
  const { busy, result, run } = useRun();
  const [pick, setPick] = useState(options[0]?.id ?? "");
  return (
    <div className="space-y-2 text-sm">
      {current.length === 0 ? (
        <p className="text-muted">No prerequisites.</p>
      ) : (
        <ul className="space-y-1">
          {current.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-2">
              <span>{p.label}</span>
              {editable && (
                <button type="button" disabled={busy} className="text-accent underline-offset-2 hover:underline" onClick={() => run(() => removePrerequisite(id, p.id))}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {editable && options.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Prerequisite concept" value={pick} onChange={(e) => setPick(e.target.value)} className="rounded-lg border border-border bg-surface px-2 py-2">
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
          <button type="button" disabled={busy || !pick} className={secondary} onClick={() => run(() => addPrerequisite(id, pick))}>
            Add prerequisite
          </button>
        </div>
      )}
      <Problems result={result} />
    </div>
  );
}

export function PublishConcept({ id }: { id: string }) {
  const { busy, result, run } = useRun();
  return (
    <div className="space-y-1">
      <button type="button" disabled={busy} className={button} onClick={() => run(() => publishConcept(id))}>
        {busy ? "Publishing…" : "Approve and publish"}
      </button>
      <Problems result={result} />
    </div>
  );
}
