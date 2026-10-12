"use client";

import { useState } from "react";

// SETTINGS-01: with data saver on, a lesson diagram loads only when the learner asks for it. Its alt text is shown
// meanwhile, so the lesson still reads without it.
export function SaverImage({ src, alt }: { src: string; alt: string }) {
  const [shown, setShown] = useState(false);
  if (shown) {
    // eslint-disable-next-line @next/next/no-img-element -- an authenticated, immutable archive copy; no optimiser
    return <img src={src} alt={alt} className="mx-auto h-auto max-w-full rounded-lg border border-border bg-white" />;
  }
  return (
    <div className="space-y-2 rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm">
      <p className="text-muted">{alt}</p>
      <button type="button" onClick={() => setShown(true)} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
        Show diagram (data saver is on)
      </button>
    </div>
  );
}
