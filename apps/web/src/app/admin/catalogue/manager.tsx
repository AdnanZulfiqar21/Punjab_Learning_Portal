"use client";

import { useActionState, useState, useTransition } from "react";
import { applyCatalogue, previewCatalogue, type ApplyState, type PreviewState } from "@/app/actions/catalogue";
import { Badge, Notice } from "@/components/ui";

const SECTIONS: [string, string][] = [
  ["chapters_added", "Chapters added"],
  ["chapters_renamed", "Chapters renamed"],
  ["chapters_reordered", "Chapters reordered"],
  ["chapters_reactivated", "Chapters brought back"],
  ["chapters_retired", "Chapters retired"],
  ["topics_added", "Topics added"],
  ["topics_renamed", "Topics renamed"],
  ["topics_moved", "Topics moved"],
  ["topics_reactivated", "Topics brought back"],
  ["topics_retired", "Topics retired"],
];
const button = "rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent disabled:opacity-60";

function describe(row: Record<string, unknown>): string {
  if ("from" in row && "to" in row) return `${String(row.title ?? "")} ${String(row.from)} → ${String(row.to)}`.trim();
  return String(row.title ?? row.id);
}

export function CatalogueManager() {
  const [state, setState] = useState<PreviewState>(undefined);
  const [pending, start] = useTransition();
  const [applied, apply, applying] = useActionState<ApplyState, FormData>(applyCatalogue, undefined);
  const p = state?.preview;
  return (
    <div className="space-y-4">
      <button type="button" className={button} disabled={pending} onClick={() => start(async () => setState(await previewCatalogue()))}>
        {pending ? "Preparing preview…" : p ? "Preview again" : "Preview changes"}
      </button>
      {state?.error && (
        <Notice tone="warn" title="No preview">
          {state.error}
        </Notice>
      )}
      {p && p.errors.length > 0 && (
        <Notice tone="danger" title="The catalogue doesn't validate">
          <ul className="list-disc pl-5">
            {p.errors.slice(0, 20).map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </Notice>
      )}
      {p && p.errors.length === 0 && (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            {p.change_count === 0 ? "The database already matches the catalogue: nothing to apply." : `${p.change_count} changes.`} Catalogue fingerprint{" "}
            <span className="font-mono">{p.input_sha256.slice(0, 12)}</span>.
          </p>
          {SECTIONS.filter(([k]) => (p.changes[k] ?? []).length > 0).map(([k, label]) => (
            <section key={k} aria-label={label} className="space-y-1">
              <h2 className="font-semibold">
                {label} ({p.changes[k].length})
              </h2>
              <ul className="list-disc pl-5 text-sm">
                {p.changes[k].slice(0, 50).map((row, i) => (
                  <li key={i}>{describe(row)}</li>
                ))}
              </ul>
              {p.changes[k].length > 50 && <p className="text-xs text-muted">…and {p.changes[k].length - 50} more.</p>}
            </section>
          ))}
          {p.dependencies.length > 0 && (
            <section aria-label="Affected content" className="space-y-1">
              <h2 className="font-semibold">Content linked to retired or moved structure ({p.dependencies.length})</h2>
              <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
                {p.dependencies.map((d) => (
                  <li key={d.item_id} className="flex flex-wrap items-center gap-2 p-2">
                    {d.published && <Badge tone="warn">Published</Badge>}
                    <span>
                      {d.kind} · {d.title} · {d.availability} · {d.reason}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {p.change_count > 0 && (
            <form action={apply} className="space-y-2 rounded-xl border border-border bg-surface p-4">
              <input type="hidden" name="input_sha256" value={p.input_sha256} />
              {p.published_dependencies > 0 && (
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" name="acknowledge" required className="mt-1" />
                  <span>
                    I&apos;ve reviewed the {p.published_dependencies} published item{p.published_dependencies === 1 ? "" : "s"} above. Their chapter or topic will be retired or
                    moved; I&apos;ll re-home or retire them separately.
                  </span>
                </label>
              )}
              <button type="submit" className={button} disabled={applying}>
                {applying ? "Applying…" : "Apply this catalogue"}
              </button>
            </form>
          )}
        </div>
      )}
      {applied?.applied && (
        <Notice tone="ok" title="Applied">
          Import batch <span className="font-mono">{applied.applied.batch_id}</span>. Preview again to confirm nothing is left to apply.
        </Notice>
      )}
      {applied?.error && (
        <Notice tone="warn" title={applied.code === "CATALOGUE_CHANGED" ? "The catalogue changed" : "Not applied"}>
          {applied.error}
        </Notice>
      )}
    </div>
  );
}
