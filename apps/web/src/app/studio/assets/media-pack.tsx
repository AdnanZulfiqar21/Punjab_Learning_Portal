"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, useSyncExternalStore } from "react";
import type { MediaPack } from "@portal/contracts";
import { Badge } from "@/components/ui";

const MAX_BYTES = 60 * 1024 * 1024;
const ACTION_LABEL: Record<string, string> = {
  create: "New asset",
  version: "New version",
  unchanged: "Unchanged",
  error: "Error",
};
const subscribe = () => () => {};

/** MEDIA-MANIFEST-01: a .zip with manifest.json → preview (every file scanned and checked, nothing written) → archive
 * all of them or none. The chosen file stays in the page, so the commit sends exactly what was previewed. */
export function MediaPackForm() {
  const router = useRouter();
  const hydrated = useSyncExternalStore(subscribe, () => true, () => false);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pack, setPack] = useState<MediaPack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);

  async function send(f: File, commit: boolean) {
    setError(null);
    if (f.size > MAX_BYTES) return setError("A media pack can be at most 60 MB. Split it into smaller packs.");
    setBusy(commit ? "commit" : "preview");
    try {
      const res = await fetch(`/studio/assets/manifest?commit=${commit}`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: f,
      });
      const body = (await res.json().catch(() => null)) as (MediaPack & { detail?: string }) | null;
      if (res.ok && body) {
        setPack(body);
        if (body.committed) router.refresh();
      } else {
        setError(body?.detail ?? "That pack couldn't be checked.");
      }
    } catch {
      setError("That pack couldn't be uploaded. Check your connection and try again.");
    } finally {
      setBusy(null);
    }
  }

  const errors = (pack?.entries ?? []).filter((e) => e.action === "error").length;
  const writes = (pack?.entries ?? []).filter((e) => e.action === "create" || e.action === "version").length;
  return (
    <section aria-labelledby="media-pack-h" className="space-y-3 rounded-xl border border-border bg-surface p-4">
      <h2 id="media-pack-h" className="font-semibold">
        Media pack
      </h2>
      <p className="text-sm text-muted">
        A .zip with <code>manifest.json</code> and the files it lists (up to 60 MB). The same pack imported again changes nothing; a changed file
        becomes that asset&apos;s next version. The format is in the content import guide (docs/content-import.md).
      </p>
      {!hydrated ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <label className="block space-y-1">
          <span className="text-sm font-medium">Pack to check</span>
          <input
            ref={input}
            type="file"
            accept=".zip,application/zip"
            disabled={busy !== null}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              setPack(null);
              if (f) void send(f, false);
            }}
            className="block text-sm"
          />
        </label>
      )}
      {busy === "preview" && <p className="text-sm text-muted">Scanning and checking every file…</p>}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {pack && (
        <div className="space-y-3">
          <p className="text-sm">
            <span className="font-medium">{pack.committed ? "Archived" : "Preview"}</span> ·{" "}
            {Object.entries(pack.counts)
              .map(([k, v]) => `${v} ${(ACTION_LABEL[k] ?? k).toLowerCase()}`)
              .join(" · ")}
          </p>
          <ul aria-label="Pack files" className="divide-y divide-border text-sm">
            {pack.entries.map((e, i) => (
              <li key={`${e.external_id}-${i}`} className="space-y-1 py-2">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{e.title || e.external_id}</span>
                  <Badge tone={e.action === "error" ? "warn" : undefined}>{ACTION_LABEL[e.action] ?? e.action}</Badge>
                  <span className="text-muted">
                    {e.external_id} · {e.file}
                  </span>
                </p>
                {e.errors.map((m) => (
                  <p key={m} className="text-danger">
                    {m}
                  </p>
                ))}
                {e.version_id && (
                  <p className="font-mono text-xs text-muted" title="Version ID for use in content">
                    Version {e.number}: {e.version_id}
                  </p>
                )}
              </li>
            ))}
          </ul>
          {!pack.committed && file && (
            <button
              type="button"
              disabled={busy !== null || errors > 0 || writes === 0}
              onClick={() => void send(file, true)}
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
            >
              {busy === "commit" ? "Archiving…" : errors > 0 ? "Fix the errors, then check the pack again" : `Archive ${writes} file${writes === 1 ? "" : "s"}`}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
