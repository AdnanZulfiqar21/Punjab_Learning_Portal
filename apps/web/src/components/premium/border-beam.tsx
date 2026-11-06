// PREMIUM-LOOK-01: Magic UI "Border Beam" pattern — a light travels round a featured card's border (CSS only).
export function BorderBeam({ duration = 8 }: { duration?: number }) {
  return <span aria-hidden className="border-beam pointer-events-none absolute inset-0 rounded-[inherit]" style={{ ["--beam-duration" as string]: `${duration}s` }} />;
}
