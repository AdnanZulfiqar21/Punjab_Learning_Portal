// PREMIUM-LOOK-01: Magic UI "Marquee" pattern — a slow endless row (CSS only; stops on hover and for reduced motion).
import type { ReactNode } from "react";

export function Marquee({ children, reverse = false, label }: { children: ReactNode; reverse?: boolean; label: string }) {
  return (
    <div className="marquee group relative flex overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]" aria-label={label} role="region">
      {[0, 1].map((i) => (
        <div key={i} aria-hidden={i === 1} className={`marquee-track flex shrink-0 gap-3 pr-3 ${reverse ? "marquee-reverse" : ""}`}>
          {children}
        </div>
      ))}
    </div>
  );
}
