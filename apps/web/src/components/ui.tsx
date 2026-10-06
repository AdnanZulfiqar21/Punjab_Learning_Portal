import Link from "next/link";
import type { ReactNode } from "react";

export function Breadcrumbs({ items }: { items: { href?: string; label: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 text-sm text-muted">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((it, i) => (
          <li key={`${it.label}-${i}`} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true">/</span>}
            {it.href ? (
              <Link href={it.href} className="underline-offset-2 hover:text-foreground hover:underline">
                {it.label}
              </Link>
            ) : (
              <span aria-current="page" className="text-foreground">
                {it.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

type Tone = "info" | "warn" | "danger" | "ok";
const TONES: Record<Tone, string> = {
  info: "border-accent/30 bg-accent-soft text-foreground",
  warn: "border-warn/30 bg-warn-soft text-foreground",
  danger: "border-danger/30 bg-danger-soft text-foreground",
  ok: "border-ok/30 bg-ok-soft text-foreground",
};

export function Notice({ tone = "info", title, children }: { tone?: Tone; title: string; children?: ReactNode }) {
  return (
    <div role={tone === "danger" ? "alert" : "note"} className={`rounded-lg border px-4 py-3 text-sm ${TONES[tone]}`}>
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-1 text-muted">{children}</div>}
    </div>
  );
}

export function Badge({ children, tone = "info" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function SkeletonLines({ lines = 4, label }: { lines?: number; label: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="h-5 animate-pulse rounded bg-surface-muted" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function SkeletonCards({ count = 6, label }: { count?: number; label: string }) {
  return (
    <div role="status" aria-live="polite" className="grid gap-3 sm:grid-cols-2">
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-xl border border-border bg-surface" />
      ))}
    </div>
  );
}
