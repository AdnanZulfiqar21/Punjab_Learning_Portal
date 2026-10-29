// DESIGN-01: the opening of a hub page. Centred (home) or start-aligned on a glass panel (a book, a section).
import type { ReactNode } from "react";

export type PageHeroProps = {
  /** Small line above the title (accent, uppercase, wide tracking). */
  eyebrow?: ReactNode;
  /** The page's h1. */
  title: ReactNode;
  /** Muted paragraph under the title. */
  lead?: ReactNode;
  /** Buttons (ButtonLink) shown under the lead. */
  actions?: ReactNode;
  /** Anything below the actions (a Continue card, stat chips). */
  children?: ReactNode;
  /** "center" for the open hero on the mesh (home); "start" for a hero on a glass panel. Default center. */
  align?: "center" | "start";
  /** Title in the accent colour (a subject's book). Default: the heading colour. */
  accentTitle?: boolean;
  /** A decoration drawn behind the content, inside the panel (aria-hidden is up to the caller). */
  backdrop?: ReactNode;
  /** id for the h1, for aria-labelledby. */
  titleId?: string;
  className?: string;
};

export function PageHero({ eyebrow, title, lead, actions, children, align = "center", accentTitle = false, backdrop, titleId, className = "" }: PageHeroProps) {
  const center = align === "center";
  return (
    <section
      aria-labelledby={titleId}
      className={`relative ${center ? "px-1 pt-10 pb-6 text-center sm:pt-16" : "glass overflow-hidden rounded-card px-6 py-8 sm:px-9 sm:py-10"} ${className}`}
    >
      {backdrop}
      <div className={`relative space-y-4 ${center ? "mx-auto max-w-3xl" : ""}`}>
        {eyebrow && <p className="text-xs font-semibold tracking-[0.15em] text-accent uppercase">{eyebrow}</p>}
        <h1
          id={titleId}
          className={`font-display text-[34px] leading-10 font-bold tracking-tight sm:text-[52px] sm:leading-14 ${accentTitle ? "text-accent" : ""}`}
        >
          {title}
        </h1>
        {lead && <p className={`text-lg text-muted sm:text-[19px] ${center ? "mx-auto max-w-2xl" : "max-w-2xl"}`}>{lead}</p>}
        {actions && <div className={`flex flex-wrap gap-3 pt-2 ${center ? "justify-center" : ""}`}>{actions}</div>}
      </div>
      {children && <div className="relative mt-8">{children}</div>}
    </section>
  );
}
