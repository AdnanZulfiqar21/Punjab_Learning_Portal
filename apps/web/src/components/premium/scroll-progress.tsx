"use client";
// PREMIUM-LOOK-01: Magic UI "Scroll Progress" without an animation library — a thin accent bar at the top shows how far
// through the lesson you are (one passive scroll listener, painted on the next frame).
import { useEffect, useRef } from "react";

export function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let raf = 0;
    const paint = () => {
      raf = 0;
      const d = document.documentElement;
      const max = d.scrollHeight - d.clientHeight;
      if (ref.current) ref.current.style.transform = `scaleX(${max > 0 ? d.scrollTop / max : 0})`;
    };
    const on = () => {
      if (!raf) raf = requestAnimationFrame(paint);
    };
    paint();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => {
      window.removeEventListener("scroll", on);
      window.removeEventListener("resize", on);
      cancelAnimationFrame(raf);
    };
  }, []);
  return <div ref={ref} aria-hidden className="fixed inset-x-0 top-0 z-50 h-1 origin-left scale-x-0 bg-gradient-to-r from-accent via-accent-strong to-accent" />;
}
