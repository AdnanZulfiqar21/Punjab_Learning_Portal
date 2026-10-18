"use client";

import { useEffect, useRef } from "react";

// Pilot: when the reader switches language, the lesson is replaced by the other variant. Both variants share one block
// structure (ids b0, b1, …), so on submit this remembers the block at the top of the screen in this tab and, once the
// other variant is on the page (a new lesson id), scrolls back to it. Without JavaScript the switch still works; it
// just starts at the top.
const KEY = "portal-keep-place";

export function KeepPlace({ lessonId }: { lessonId: string }) {
  const marker = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    let wanted: string | null = null;
    try {
      wanted = window.sessionStorage.getItem(KEY);
      if (wanted) window.sessionStorage.removeItem(KEY);
    } catch {
      // Private browsing or blocked storage: the lesson simply opens at the top.
    }
    if (!wanted || !/^b\d{1,3}$/.test(wanted)) return;
    const id = wanted;
    const go = () => document.getElementById(id)?.scrollIntoView({ block: "start" });
    const frame = requestAnimationFrame(go);
    const later = setTimeout(go, 350); // after any scroll the router itself does on arrival
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(later);
    };
  }, [lessonId]);

  useEffect(() => {
    const form = marker.current?.closest("form");
    if (!form) return;
    const onSubmit = () => {
      const blocks = Array.from(document.querySelectorAll<HTMLElement>("[data-block]"));
      const top = blocks.filter((b) => b.getBoundingClientRect().top <= 80).at(-1);
      try {
        if (top) window.sessionStorage.setItem(KEY, top.id);
      } catch {
        // see above
      }
    };
    form.addEventListener("submit", onSubmit);
    return () => form.removeEventListener("submit", onSubmit);
  }, []);

  return <span ref={marker} hidden />;
}
