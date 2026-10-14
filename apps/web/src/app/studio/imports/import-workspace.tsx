"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore, useTransition } from "react";
import type { ImportBatch } from "@portal/contracts";
import { commitImport, discardImport, getImport } from "@/app/actions/imports";
import { Badge } from "@/components/ui";

const MAX_BYTES = 5 * 1024 * 1024;
const BULK_MAX_BYTES = 50 * 1024 * 1024; // IMPORT-BULK-01: larger files are checked by the import worker
const WORKING = new Set(["queued", "validating", "committing"]);
const SHOWN_ROWS = 500;
const STATUS_TITLE: Record<string, string> = {
  queued: "Queued",
  validating: "Checking",
  previewed: "Preview",
  committing: "Importing",
  committed: "Imported",
  discarded: "Discarded",
  failed: "Failed",
};
const ACTION_LABEL: Record<string, string> = {
  create: "New draft",
  update: "Update draft",
  unchanged: "Unchanged",
  skip: "Skipped",
  error: "Error",
};

/** Upload → preview (dry run) → commit. Shows every row's action, errors and warnings. */
const subscribe = () => () => {};

export function ImportWorkspace({ initialBatchId }: { initialBatchId?: string } = {}) {
  // The picker appears only once the page is interactive, so a file chosen early is never silently ignored.
  const hydrated = useSyncExternalStore(subscribe, () => true, () => false);
  const input = useRef<HTMLInputElement>(null);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pending, start] = useTransition();

  // Reopened from the recent imports list (IMPORT-BULK-01): load that batch once.
  useEffect(() => {
    if (!initialBatchId) return;
    void getImport(initialBatchId).then((out) => (out.ok ? setBatch(out.batch) : setError(out.error)));
  }, [initialBatchId]);

  // While the import worker has the batch, show its progress (every 2 seconds) until it is ready, imported or failed.
  const working = batch !== null && WORKING.has(batch.status);
  const batchId = batch?.id;
  useEffect(() => {
    if (!working || !batchId) return;
    const timer = setInterval(async () => {
      const out = await getImport(batchId);
      if (out.ok) setBatch(out.batch);
    }, 2000);
    return () => clearInterval(timer);
  }, [working, batchId]);

  async function preview(file: File) {
    setError(null);
    setBatch(null);
    if (file.size > BULK_MAX_BYTES) return setError("Import files can be at most 50 MB. Split the file.");
    const name = file.name.toLowerCase();
    const format = name.endsWith(".csv") ? "csv" : name.endsWith(".xlsx") ? "xlsx" : "json";
    setUploading(true);
    try {
      const send = (bulk: boolean) =>
        fetch(`/studio/imports/upload?${new URLSearchParams({ format, filename: file.name, ...(bulk ? { bulk: "1" } : {}) }).toString()}`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file,
        });
      let res = await send(file.size > MAX_BYTES);
      if (res.status === 413 && file.size <= MAX_BYTES) res = await send(true); // more rows than a quick preview takes
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
  // A bulk preview can hold thousands of rows: past 500, list the rows that need attention; the report has them all.
  const allRows = batch?.rows ?? [];
  const listed = allRows.length > SHOWN_ROWS ? allRows.filter((r) => r.errors.length > 0 || r.warnings.length > 0).slice(0, SHOWN_ROWS) : allRows;
  const writes = (batch?.rows ?? []).filter((r) => r.action === "create" || r.action === "update").length ?? 0;
  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <label htmlFor="import-file" className="font-medium">
          File to preview <span className="text-sm font-normal text-muted">(JSON, CSV or Excel .xlsx, up to 5 MB)</span>
        </label>
        {!hydrated ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
        <input
          ref={input}
          id="import-file"
          type="file"
          accept=".json,.csv,.xlsx,application/json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          disabled={uploading}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void preview(f);
          }}
          className="block text-sm"
        />
        )}
        <p className="text-sm text-muted">
          Multiple-choice template, headings only:{" "}
          <a href="/studio/imports/templates/mcq.xlsx" download className="text-accent underline underline-offset-2">
            Excel (.xlsx)
          </a>{" "}
          ·{" "}
          <a href="/studio/imports/templates/mcq.csv" download className="text-accent underline underline-offset-2">
            CSV
          </a>
          . The formats are described in the content import guide (docs/content-import.md).
        </p>
        {uploading && <p className="text-sm text-muted">Uploading and checking…</p>}
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
              {STATUS_TITLE[batch.status] ?? "Preview"}: {batch.filename}
            </h2>
            <p className="text-sm text-muted">
              {Object.entries(batch.counts)
                .filter(([k]) => !k.startsWith("written_"))
                .map(([k, v]) => `${v} ${(ACTION_LABEL[k] ?? k).toLowerCase()}`)
                .join(" · ")}
            </p>
          </div>
          {WORKING.has(batch.status) && (
            <p role="status" className="text-sm">
              {batch.status === "queued"
                ? "Waiting for the import worker. Large files are checked in the background; you can leave this page and come back."
                : batch.status === "validating"
                  ? `Checking rows: ${batch.rows_checked ?? 0} of ${batch.rows_total ?? "?"}.`
                  : `Importing ${batch.rows_total ?? ""} rows as drafts. Every row is written, or none.`}
            </p>
          )}
          {batch.status === "failed" && (
            <p role="alert" className="text-sm text-danger">
              {batch.failure ?? "This import failed."}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {batch.status === "queued" && (
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
                Cancel
              </button>
            )}
            {!WORKING.has(batch.status) && batch.status !== "failed" && (
            <a href={`/studio/imports/${batch.id}/report`} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent">
              Download correction report
            </a>
            )}
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
          {listed.length < allRows.length && (
            <p className="text-sm text-muted">
              Showing the {listed.length} row{listed.length === 1 ? "" : "s"} with errors or warnings out of {allRows.length}. The correction report lists every row.
            </p>
          )}
          <ol className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Import rows">
            {listed.map((r) => (
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
