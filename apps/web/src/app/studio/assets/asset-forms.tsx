"use client";

import { useRouter } from "next/navigation";
import { useActionState, useState } from "react";
import { createAsset } from "@/app/actions/studio";

const field = "rounded-lg border border-border bg-surface px-3 py-2";
const button = "rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

export function NewAsset({ grade, subject }: { grade: number; subject: string }) {
  const router = useRouter();
  const [state, action, pending] = useActionState(async (prev: { error?: string } | undefined, form: FormData) => {
    const out = await createAsset(prev, form);
    if (!out?.error) router.refresh();
    return out;
  }, undefined);
  return (
    <form action={action} className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-surface p-4">
      <input type="hidden" name="grade" value={grade} />
      <input type="hidden" name="subject" value={subject} />
      <label className="space-y-1">
        <span className="block text-sm font-medium">New asset</span>
        <input name="title" required minLength={2} maxLength={200} placeholder="Title" className={field} />
      </label>
      <label className="space-y-1">
        <span className="block text-sm font-medium">Kind</span>
        <select name="kind" defaultValue="image" className={field}>
          <option value="image">Image or diagram (PNG, JPEG)</option>
          <option value="handout">Handout (PDF)</option>
          <option value="caption">Captions (WebVTT)</option>
          <option value="diagram_source">Diagram source (archived, never served)</option>
        </select>
      </label>
      <button type="submit" disabled={pending} className={button}>
        {pending ? "Creating…" : "Create"}
      </button>
      {state?.error && (
        <p role="alert" className="w-full text-sm text-danger">
          {state.error}
        </p>
      )}
    </form>
  );
}

export function UploadVersion({ assetId }: { assetId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(form: FormData) {
    const file = form.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Choose a file.");
      return;
    }
    setBusy(true);
    setError(null);
    const qs = new URLSearchParams();
    for (const k of ["source", "author", "licence"]) qs.set(k, String(form.get(k) ?? ""));
    try {
      const res = await fetch(`/studio/assets/${assetId}/upload?${qs.toString()}`, { method: "POST", body: file });
      if (!res.ok) {
        const p = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(p?.detail ?? `Upload failed (${res.status}).`);
        return;
      }
      router.refresh();
    } catch {
      setError("Can't reach the service. Nothing was uploaded; try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="text-sm">
      <summary className="cursor-pointer font-medium">Upload a new version</summary>
      <form action={upload} className="mt-3 flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block">File</span>
          <input type="file" name="file" required className="text-sm" />
        </label>
        <label className="space-y-1">
          <span className="block">Source (who made it, from what)</span>
          <input name="source" required minLength={3} maxLength={500} className={field} />
        </label>
        <label className="space-y-1">
          <span className="block">Author</span>
          <input name="author" maxLength={200} className={field} />
        </label>
        <label className="space-y-1">
          <span className="block">Licence</span>
          <input name="licence" maxLength={200} className={field} />
        </label>
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Uploading…" : "Upload"}
        </button>
        {error && (
          <p role="alert" className="w-full text-danger">
            {error}
          </p>
        )}
      </form>
    </details>
  );
}
