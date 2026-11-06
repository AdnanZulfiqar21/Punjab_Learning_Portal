// PREMIUM-LOOK-01: Magic UI "Shimmer Button" pattern as a link — a light sweeps across the dark pill.
import Link from "next/link";
import type { ReactNode } from "react";

export function ShimmerLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="shimmer relative inline-flex min-h-12 items-center gap-2 overflow-hidden rounded-full bg-foreground px-6 text-[15px] font-semibold text-background shadow-glass transition hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
    >
      {children}
    </Link>
  );
}
