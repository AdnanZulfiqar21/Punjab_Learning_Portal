"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

const MAX_BYTES = 5 * 1024 * 1024;

export type Shot = { id: string; width: number; height: number };

/** Thumbnails of a request's screenshots; each opens the full image in a new tab. */
export function ScreenshotList({ ticketId, shots }: { ticketId: string; shots: Shot[] }) {
  if (shots.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-3" aria-label="Screenshots">
      {shots.map((s, i) => (
        <li key={s.id}>
          <a href={`/help/${ticketId}/screenshots/${s.id}`} target="_blank" rel="noopener" className="block rounded-lg border border-border hover:border-accent">
            {/* eslint-disable-next-line @next/next/no-img-element -- private, uncached evidence served by our own route */}
            <img src={`/help/${ticketId}/screenshots/${s.id}`} alt={`Screenshot ${i + 1}`} width={s.width} height={s.height} className="h-24 w-auto rounded-lg object-contain" />
          </a>
        </li>
      ))}
    </ul>
  );
}

/** Lets the learner add a JPEG or PNG screenshot (at most 5 MB) to an open request. */
export function AddScreenshot({ ticketId, remaining }: { ticketId: string; remaining: number }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  if (remaining <= 0) return <p className="text-sm text-muted">This request has the most screenshots it can hold.</p>;
  async function upload(file: File) {
    setError(null);
    if (!["image/png", "image/jpeg"].includes(file.type)) return setError("Choose a PNG or JPEG screenshot.");
    if (file.size > MAX_BYTES) return setError("Screenshots can be at most 5 MB.");
    setPending(true);
    try {
      const res = await fetch(`/help/${ticketId}/screenshots`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file });
      if (res.ok) router.refresh();
      else setError(((await res.json().catch(() => null)) as { detail?: string } | null)?.detail ?? "That screenshot couldn't be added.");
    } catch {
      setError("That screenshot couldn't be added. Check your connection and try again.");
    } finally {
      setPending(false);
      if (input.current) input.current.value = "";
    }
  }
  return (
    <div className="space-y-1">
      <label htmlFor="screenshot" className="font-medium">
        Add a screenshot <span className="text-sm font-normal text-muted">(PNG or JPEG, up to 5 MB; {remaining} left)</span>
      </label>
      <input
        ref={input}
        id="screenshot"
        type="file"
        accept="image/png,image/jpeg"
        disabled={pending}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void upload(f);
        }}
        className="block text-sm"
      />
      {pending && <p className="text-sm text-muted">Checking and adding your screenshot…</p>}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
