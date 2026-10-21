"use client";

import { useEffect, useRef } from "react";

// Pilot: when the reader switches language, the lesson is replaced by the other variant. Both variants share one block
// structure (ids b0, b1, …), so on submit this remembers the block at the top of the screen in this tab and, once the
// other variant is on the page (a new lesson id), scrolls back to it. Without JavaScript the switch still works; it
// just starts at the top.
const KEY = "portal-keep-place";

export function KeepPlace({ lessonId }: { lessonId: string }) {
  const marker = useRef<HTMLSpanElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // The note is "b6|<time>": it is cleared once the block has been reached (not on read, so a development
    // double-invoked effect can't lose it), and ignored when older than a moment.
    let wanted: string | null = null;
    try {
      const raw = window.sessionStorage.getItem(KEY) ?? "";
      const [id, at] = raw.split("|");
      if (/^b\d{1,3}$/.test(id) && Date.now() - Number(at) < 15_000) wanted = id;
      else if (raw) window.sessionStorage.removeItem(KEY);
    } catch {
      // Private browsing or blocked storage: the lesson simply opens at the top.
    }
    if (!wanted) return;
    const id = wanted;
    // The router may scroll on arrival after this effect, and the lesson may still be streaming in: keep returning
    // to the block for a moment, and stop as soon as it sits at the top.
    const timers: ReturnType<typeof setTimeout>[] = [];
    const go = () => {
      const el = document.getElementById(id);
      if (!el) return;
      if (Math.abs(el.getBoundingClientRect().top - 80) > 4) el.scrollIntoView({ block: "start" });
      try {
        window.sessionStorage.removeItem(KEY);
      } catch {
        // see above
      }
    };
    const frame = requestAnimationFrame(go);
    for (const ms of [150, 350, 700, 1200, 2000]) timers.push(setTimeout(go, ms));
    return () => {
      cancelAnimationFrame(frame);
      timers.forEach(clearTimeout);
    };
  }, [lessonId]);

  // Listen on the document: the form's DOM node is replaced after each switch, while this component is kept.
  useEffect(() => {
    const onSubmit = (e: Event) => {
      if (e.target !== marker.current?.closest("form")) return;
      const blocks = Array.from(document.querySelectorAll<HTMLElement>("[data-block]"));
      const top = blocks.filter((b) => b.getBoundingClientRect().top <= 80).at(-1);
      if (input.current) input.current.value = top?.id ?? "";
      try {
        if (top) window.sessionStorage.setItem(KEY, `${top.id}|${Date.now()}`);
      } catch {
        // see above
      }
    };
    document.addEventListener("submit", onSubmit, true);
    return () => document.removeEventListener("submit", onSubmit, true);
  }, []);

  return (
    <>
      <span ref={marker} hidden />
      <input ref={input} type="hidden" name="block" defaultValue="" />
    </>
  );
}
