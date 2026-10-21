"use client";

// REGION-MAP-01 (W03.S2.T2): mark where on a page an answer is. The area is a fraction of the page as shown (its turn
// and trim applied); the server keeps it in the original page's coordinates, so turning the page later doesn't move it.
// Every area can be chosen without a pointer (the preset buttons); dragging on the picture is a finer alternative.
import { useRef, useState } from "react";
import { AreaOverlay } from "@/components/area-overlay";
import type { Box } from "@/lib/page-areas";

export { AreaOverlay };

const PRESETS: { label: string; box: Box }[] = [
  { label: "Top half", box: [0, 0, 1, 0.5] },
  { label: "Bottom half", box: [0, 0.5, 1, 0.5] },
  { label: "Top third", box: [0, 0, 1, 0.3334] },
  { label: "Middle third", box: [0, 0.3333, 1, 0.3334] },
  { label: "Bottom third", box: [0, 0.6666, 1, 0.3334] },
];
const MIN = 0.02;

export function AreaPicker({
  src,
  pageLabel,
  answerLabel,
  onSave,
  onCancel,
}: {
  src: string;
  pageLabel: string;
  answerLabel: string;
  onSave: (box: Box) => void;
  onCancel: () => void;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const start = useRef<[number, number] | null>(null);
  const [box, setBox] = useState<Box | null>(null);

  const at = (e: React.PointerEvent): [number, number] => {
    const r = frame.current!.getBoundingClientRect();
    return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))];
  };
  const usable = box !== null && box[2] >= MIN && box[3] >= MIN;

  return (
    <div role="group" aria-label={`Mark the area of ${answerLabel} on ${pageLabel}`} className="space-y-2 rounded-lg border border-border bg-surface-muted p-3">
      <p className="text-sm">
        Choose where {answerLabel} is on {pageLabel}: pick a part of the page, or drag a box over the picture.
      </p>
      <div className="flex flex-wrap gap-2 text-sm">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" onClick={() => setBox(p.box)} className="rounded border border-border bg-surface px-2 py-1 hover:bg-surface-muted">
            {p.label}
          </button>
        ))}
      </div>
      <div
        ref={frame}
        className="relative mx-auto w-full max-w-md touch-none select-none"
        onPointerDown={(e) => {
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          start.current = at(e);
          setBox(null);
        }}
        onPointerMove={(e) => {
          if (!start.current) return;
          const [x0, y0] = start.current;
          const [x1, y1] = at(e);
          setBox([Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0)]);
        }}
        onPointerUp={() => {
          start.current = null;
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- private, uncached preview served by our own route */}
        <img src={src} alt={pageLabel} className="w-full rounded" draggable={false} />
        {box && <AreaOverlay boxes={[box]} />}
      </div>
      <p className="flex gap-3 text-sm">
        <button
          type="button"
          disabled={!usable}
          onClick={() => box && onSave(box)}
          className="rounded bg-accent px-3 py-1 font-medium text-white disabled:opacity-60 dark:text-background"
        >
          Save this area
        </button>
        <button type="button" onClick={onCancel} className="text-muted underline underline-offset-2">
          Cancel
        </button>
      </p>
    </div>
  );
}
