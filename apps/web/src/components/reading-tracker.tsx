"use client";

import { useEffect, useRef } from "react";
import { saveReadingPosition } from "@/app/actions/lessons";

// LESSON-PROGRESS-01 (P11.S2.T1): remembers which lesson the learner is reading, for "continue where you left off" on
// any device. A lesson counts once its heading has been in the upper part of the screen for a moment; the server keeps
// only the newest place, so a slower tab or device never moves it back.
export function ReadingTracker({ lessonIds }: { lessonIds: string[] }) {
  const last = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    const headings = lessonIds.map((id) => document.getElementById(`lesson-${id}`)).filter((h): h is HTMLElement => h !== null);
    if (headings.length === 0 || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const seen = entries.filter((e) => e.isIntersecting).map((e) => e.target.id.replace(/^lesson-/, ""));
        if (seen.length === 0) return;
        const id = seen[seen.length - 1];
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => {
          if (id === last.current) return;
          last.current = id;
          void saveReadingPosition(id).catch(() => undefined); // best effort: reading never waits on it
        }, 2000);
      },
      { rootMargin: "0px 0px -50% 0px" },
    );
    headings.forEach((h) => observer.observe(h));
    return () => {
      observer.disconnect();
      if (timer.current) clearTimeout(timer.current);
    };
  }, [lessonIds]);
  return null;
}
