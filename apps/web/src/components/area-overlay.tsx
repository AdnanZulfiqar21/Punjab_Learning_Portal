// REGION-MAP-01 (W03.S2.T2): outlines of marked answer areas over a page picture. Boxes are fractions of the page as
// shown, so the outline sits on the same place at any size; the parent is positioned (relative).
import type { Box } from "@/lib/page-areas";

export function AreaOverlay({ boxes, label }: { boxes: Box[]; label?: string }) {
  return (
    <>
      {boxes.map((b, i) => (
        <span
          key={i}
          aria-hidden
          className="pointer-events-none absolute rounded-sm border-2 border-accent bg-accent/10"
          style={{ left: `${b[0] * 100}%`, top: `${b[1] * 100}%`, width: `${b[2] * 100}%`, height: `${b[3] * 100}%` }}
        >
          {label && <span className="absolute left-0 top-0 bg-accent px-1 text-xs text-white dark:text-background">{label}</span>}
        </span>
      ))}
    </>
  );
}
