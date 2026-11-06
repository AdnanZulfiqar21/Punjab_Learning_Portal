"use client";
// PREMIUM-LOOK-01: Magic UI "Magic Card" pattern without an animation library — a soft spotlight in the card's own
// accent follows the pointer (two CSS variables set on pointer move).
import type { ReactNode } from "react";
// Plain class joining: tailwind-merge would ship ~8 KB to the browser for no conflicts.

export function SpotlightCard({ children, className, ...rest }: { children: ReactNode; className?: string } & Record<`data-${string}`, string>) {
  return (
    <div
      {...rest}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--spot-x", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--spot-y", `${e.clientY - r.top}px`);
      }}
      className={`spotlight group glass relative overflow-hidden rounded-card transition duration-300 hover:-translate-y-0.5 hover:shadow-[0_18px_50px_-20px_color-mix(in_oklab,var(--accent)_55%,transparent)] motion-reduce:hover:translate-y-0 ${className ?? ""}`}
    >
      <div className="relative">{children}</div>
    </div>
  );
}
