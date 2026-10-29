// DESIGN-01: a section's heading with an optional line under it and an optional action on the right ("See all").
import type { ReactNode } from "react";

export type SectionHeaderProps = {
  /** id of the heading, for the section's aria-labelledby. */
  id: string;
  title: ReactNode;
  description?: ReactNode;
  /** A link or button aligned to the end of the heading row. */
  action?: ReactNode;
  /** Heading level (default 2). */
  level?: 2 | 3;
  className?: string;
};

export function SectionHeader({ id, title, description, action, level = 2, className = "" }: SectionHeaderProps) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <div className={`mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-1 ${className}`}>
      <div className="space-y-1">
        <H id={id} className={`font-display font-semibold tracking-tight ${level === 2 ? "text-2xl" : "text-lg"}`}>
          {title}
        </H>
        {description && <p className="max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {action && <div className="text-sm">{action}</div>}
    </div>
  );
}
