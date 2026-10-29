// DESIGN-01: a small glass pill for a real figure ("12 chapters"). Only ever show numbers the API returned (owner rule 6).
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";

export function StatChip({ children, icon, className = "" }: { children: ReactNode; icon?: IconName; className?: string }) {
  return (
    <span className={`glass inline-flex min-h-8 items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium text-foreground shadow-none ${className}`}>
      {icon && <Icon name={icon} size={16} className="text-accent" />}
      {children}
    </span>
  );
}
