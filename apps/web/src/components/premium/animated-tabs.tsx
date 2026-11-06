"use client";
// PREMIUM-LOOK-01: Motion Primitives "Animated Background" pattern without an animation library — the dark pill slides
// to the chosen view (English | Roman Urdu | Video Solution) with a CSS transition. Each tab is a real link, so it
// works without JavaScript too (the chosen link then carries the pill colours itself).
import Link from "next/link";
import { useLayoutEffect, useRef, type ReactNode } from "react";

export type TabItem = { key: string; label: string; href: string; icon?: ReactNode; lang?: string };

export function AnimatedTabs({ items, active, label }: { items: TabItem[]; active: string; label: string }) {
  const nav = useRef<HTMLElement>(null);
  const pill = useRef<HTMLSpanElement>(null);
  const moveTo = (key: string) => {
    const el = nav.current?.querySelector<HTMLElement>(`[data-tab="${key}"]`);
    const p = pill.current;
    if (!el || !p) return;
    Object.assign(p.style, { left: `${el.offsetLeft}px`, top: `${el.offsetTop}px`, width: `${el.offsetWidth}px`, height: `${el.offsetHeight}px`, opacity: "1" });
    nav.current?.querySelectorAll<HTMLElement>("[data-tab]").forEach((t) => t.toggleAttribute("data-on", t === el));
  };
  useLayoutEffect(() => {
    moveTo(active);
    nav.current?.setAttribute("data-ready", "");
  });
  return (
    <nav ref={nav} aria-label={label} className="glass relative inline-flex flex-wrap gap-1 rounded-full p-1.5">
      <span
        ref={pill}
        aria-hidden
        className="absolute rounded-full bg-foreground opacity-0 shadow-glass transition-all duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
      />
      {items.map((t) => (
        <Link
          key={t.key}
          data-tab={t.key}
          data-on={t.key === active ? "" : undefined}
          href={t.href}
          scroll={false}
          aria-current={t.key === active ? "page" : undefined}
          lang={t.lang}
          onClick={() => moveTo(t.key)}
          className={
            "relative z-10 inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-semibold text-muted transition-colors duration-200 hover:text-foreground sm:px-5 " +
            "data-[on]:text-background data-[on]:hover:text-background [nav:not([data-ready])_&]:data-[on]:bg-foreground"
          }
        >
          {t.icon}
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
