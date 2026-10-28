"use client";

import { useState, type KeyboardEvent, type PointerEvent } from "react";

// A `model3d` block on the web (renderer 2): a labelled poster render first, then a turntable the reader turns by
// dragging or with the arrow keys (pre-rendered frames, one full turn). No live 3D engine ships to learners, so the
// lesson page stays within its JavaScript budget and the figure works under data saver.
const PX_PER_FRAME = 22;

export function Model3DFigure({
  poster,
  frames,
  alt,
  caption,
  labels,
  longDescription,
  dataSaver,
}: {
  poster: string;
  frames: string[];
  alt: string;
  caption: string;
  labels: string[];
  longDescription: string;
  dataSaver: boolean;
}) {
  const [mode, setMode] = useState<"poster" | "turntable">("poster");
  const [shown, setShown] = useState(!dataSaver);
  const [frame, setFrame] = useState(0);
  const [drag, setDrag] = useState<{ x: number; start: number } | null>(null);
  const count = frames.length;
  const turn = (step: number) => setFrame((f) => (((f + step) % count) + count) % count);

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ x: e.clientX, start: frame });
  }
  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!drag || !count) return;
    const step = Math.round((e.clientX - drag.x) / PX_PER_FRAME);
    setFrame((((drag.start - step) % count) + count) % count);
  }
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "ArrowRight") turn(1);
    else if (e.key === "ArrowLeft") turn(-1);
    else return;
    e.preventDefault();
  }

  const plate = "overflow-hidden rounded-xl border border-border bg-white";
  return (
    <figure className="space-y-2">
      <p className="flex items-center gap-2 text-sm text-muted">
        <span className="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold">3D model</span>
        {mode === "turntable" ? "Drag left or right, or use the arrow keys, to turn it." : "Choose “Rotate the model” to turn it."}
      </p>
      {mode === "poster" ? (
        shown ? (
          <div className={plate}>
            {/* A lazy image with no size is 0×0 until it loads, so whether it ever starts loading is a matter of timing
                (it made the pilot e2e journey flaky). Full width and a minimum height give it a box from the start. */}
            {/* eslint-disable-next-line @next/next/no-img-element -- an authenticated, immutable archive copy; no optimiser */}
            <img src={poster} alt={alt} loading="lazy" className="mx-auto h-auto min-h-40 w-full max-w-full object-contain" />
          </div>
        ) : (
          <div className="space-y-2 rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm">
            <p className="text-muted">{alt}</p>
            <button type="button" onClick={() => setShown(true)} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
              Show model (data saver is on)
            </button>
          </div>
        )
      ) : (
        <div
          role="slider"
          tabIndex={0}
          aria-label={`${alt} Turntable: use the arrow keys to turn it.`}
          aria-valuemin={1}
          aria-valuemax={count}
          aria-valuenow={frame + 1}
          aria-valuetext={`Frame ${frame + 1} of ${count}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={() => setDrag(null)}
          onPointerCancel={() => setDrag(null)}
          onKeyDown={onKeyDown}
          className={`${plate} relative aspect-[4/3] cursor-ew-resize touch-pan-y select-none focus:outline-accent`}
        >
          {frames.map((src, i) => (
            // eslint-disable-next-line @next/next/no-img-element -- archive copies, swapped by opacity for a smooth turn
            <img key={src} src={src} alt="" draggable={false} className={`absolute inset-0 h-full w-full object-contain ${i === frame ? "" : "opacity-0"}`} />
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {count > 0 && mode === "poster" && (
          <button type="button" onClick={() => setMode("turntable")} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
            Rotate the model
          </button>
        )}
        {mode === "turntable" && (
          <>
            <button type="button" aria-label="Turn left" onClick={() => turn(-1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
              ‹
            </button>
            <button type="button" aria-label="Turn right" onClick={() => turn(1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
              ›
            </button>
            <button type="button" onClick={() => setMode("poster")} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent">
              Show labels
            </button>
          </>
        )}
      </div>
      {labels.length > 0 && (
        <ul className="flex flex-wrap gap-1.5 text-xs" aria-label="Labels">
          {labels.map((l) => (
            <li key={l} className="rounded-full border border-border px-2 py-0.5 text-muted">
              {l}
            </li>
          ))}
        </ul>
      )}
      {caption && <figcaption className="text-sm text-muted">{caption}</figcaption>}
      {longDescription && (
        <details className="text-sm">
          <summary className="cursor-pointer">Describe this model</summary>
          <p className="mt-1 whitespace-pre-line text-muted">{longDescription}</p>
        </details>
      )}
    </figure>
  );
}
