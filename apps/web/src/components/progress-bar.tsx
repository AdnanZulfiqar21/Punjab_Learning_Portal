// DESIGN-01: a labelled progress bar (role="progressbar") with the accent gradient. Only for real values from the API;
// never a made-up percentage (owner rule 6).

export type ProgressBarProps = {
  /** Current value, between 0 and max. Values outside are clamped. */
  value: number;
  /** Default 100. */
  max?: number;
  /** The accessible name ("Syllabus coverage"). */
  label: string;
  /** Spoken value, when "40%" is not the right reading ("11 of 18 topics"). */
  valueText?: string;
  className?: string;
};

export function ProgressBar({ value, max = 100, label, valueText, className = "" }: ProgressBarProps) {
  const safeMax = max > 0 ? max : 100;
  const now = Math.min(Math.max(Number.isFinite(value) ? value : 0, 0), safeMax);
  const percent = (now / safeMax) * 100;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={safeMax}
      aria-valuenow={now}
      aria-valuetext={valueText}
      className={`h-1.5 overflow-hidden rounded-full bg-[var(--track)] ${className}`}
    >
      <div
        className="h-full rounded-full"
        style={{
          width: `${percent}%`,
          background: "linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 70%, white))",
        }}
      />
    </div>
  );
}
