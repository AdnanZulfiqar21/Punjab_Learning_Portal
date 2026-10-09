"use client";

import Link from "next/link";
import { useRef, useState, useTransition } from "react";
import type { ImportBatch } from "@portal/contracts";
import { commitImport, discardImport } from "@/app/actions/imports";
import { Badge } from "@/components/ui";

const MAX_BYTES = 5 * 1024 * 1024;
const ACTION_LABEL: Record<string, string> = {
  create: "New draft",
  update: "Update draft",
  unchanged: "Unchanged",
  skip: "Skipped",
  error: "Error",
};

/** Upload → preview (dry run) → commit. Shows every row's action, errors and warnings. */
export function ImportWorkspace() {
  const input = useRef<HTMLInputElement>(null);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pending, start] = useTransition();

  async function preview(file: File) {
    setError(null);
    setBatch(null);
    if (file.size > MAX_BYTES) return setError("Import files can be at most 5 MB. Split the file.");
    const format = file.name.toLowerCase().endsWith(".csv") ? "csv" : "json";
    setUploading(true);
    try {
      const qs = new URLSearchParams({ format, filename: file.name });
      const res = await fetch(`/studio/imports/upload?${qs.toString()}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
      const body = (await res.json().catch(() => null)) as (ImportBatch & { detail?: string }) | null;
      if (res.ok && body) setBatch(body);
      else setError(body?.detail ?? "That file couldn't be previewed.");
    } catch {
      setError("That file couldn't be uploaded. Check your connection and try again.");
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  const errors = (batch?.rows ?? []).filter((r) => r.action === "error").length ?? 0;
  const writes = (batch?.rows ?? []).filter((r) => r.action === "create" || r.action === "update").length ?? 0;
  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <label htmlFor="import-file" className="font-medium">
          File to preview <span className="text-sm font-normal text-muted">(JSON or CSV, up to 5 MB)</span>
        </label>
        <input
          ref={input}
          id="import-file"
          type="file"
          accept=".json,.csv,application/json,text/csv"
          disabled={uploading}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void preview(f);
          }}
          className="block text-sm"
        />
        <p className="text-sm text-muted">The formats are described in the content import guide (docs/content-import.md).</p>
        {uploading && <p className="text-sm text-muted">Checking every row…</p>}
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {batch && (
        <section aria-labelledby="preview-h" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="preview-h" className="font-semibold">
              {batch.status === "committed" ? "Imported" : batch.status === "discarded" ? "Discarded" : "Preview"}: {batch.filename}
            </h2>
            <p className="text-sm text-muted">
              {Object.entries(batch.counts)
                .filter(([k]) => !k.startsWith("written_"))
                .map(([k, v]) => `${v} ${(ACTION_LABEL[k] ?? k).toLowerCase()}`)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={`/studio/imports/${batch.id}/report`} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent">
              Download correction report
            </a>
            {batch.status === "previewed" && (
              <>
                <button
                  type="button"
                  disabled={pending || errors > 0 || writes === 0}
                  onClick={() =>
                    start(async () => {
                      setError(null);
                      const out = await commitImport(batch.id);
                      if (out.ok) setBatch(out.batch);
                      else setError(out.error);
                    })
                  }
                  className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
                >
                  {pending ? "Importing…" : `Import ${writes} row${writes === 1 ? "" : "s"} as drafts`}
                </button>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() =>
                    start(async () => {
                      const out = await discardImport(batch.id);
                      if (out.ok) setBatch({ ...batch, status: "discarded" });
                      else setError(out.error ?? null);
                    })
                  }
                  className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent"
                >
                  Discard
                </button>
              </>
            )}
          </div>
          {batch.status === "previewed" && errors > 0 && (
            <p className="text-sm text-danger">
              {errors} row{errors === 1 ? " has" : "s have"} errors. Fix the file and preview it again; nothing is imported until every row is valid.
            </p>
          )}
          <ol className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Import rows">
            {(batch.rows ?? []).map((r) => (
              <li key={r.row} className="space-y-1 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-muted">Row {r.row}</span>
                  <span className="font-medium">{r.external_id ?? "(no external_id)"}</span>
                  <Badge tone={r.action === "error" ? "danger" : r.action === "skip" ? "warn" : r.action === "unchanged" ? "info" : "ok"}>{ACTION_LABEL[r.action]}</Badge>
                  {r.item_id && (
                    <Link href={`/studio/items/${r.item_id}`} className="text-accent underline underline-offset-2">
                      Open
                    </Link>
                  )}
                </div>
                {r.errors.length > 0 && (
                  <ul className="list-disc pl-5 text-danger">
                    {r.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                )}
                {r.warnings.length > 0 && (
                  <ul className="list-disc pl-5 text-muted">
                    {r.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
