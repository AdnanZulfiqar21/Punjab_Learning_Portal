"use client";

import { useEffect, useRef } from "react";
import { mapPlace } from "@/lib/variant-place";

// Pilot: when the reader switches language, the lesson is replaced by the other variant. The variants no longer share
// one block structure (the English lesson carries only the book; Roman Urdu adds our explanations), so on submit this
// remembers the block at the top of the screen with the signatures of this variant's blocks, and once the other
// variant is on the page (a new lesson id) it scrolls to the matching block (READER-PLACE-01, lib/variant-place.ts).
// Without JavaScript the switch still works; it just starts at the top.
const KEY = "portal-keep-place";

type Note = { index: number; signatures: string[]; lessonId: string; at: number };

function readNote(): Note | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    const note = JSON.parse(raw) as Note;
    if (typeof note.index === "number" && Array.isArray(note.signatures) && Date.now() - note.at < 15_000) return note;
    window.sessionStorage.removeItem(KEY);
  } catch {
    // Private browsing, blocked storage or an old note: the lesson simply opens at the top.
  }
  return null;
}

export function KeepPlace({ lessonId, signatures }: { lessonId: string; signatures: string[] }) {
  const marker = useRef<HTMLSpanElement>(null);
  const current = useRef({ lessonId, signatures });
  useEffect(() => {
    current.current = { lessonId, signatures };
  }, [lessonId, signatures]);

  useEffect(() => {
    // The note is cleared once the block has been reached (not on read, so a development double-invoked effect can't
    // lose it), and ignored when older than a moment or written for this same lesson.
    const note = readNote();
    if (!note || note.lessonId === lessonId) return;
    const id = `b${mapPlace(note.signatures, signatures, note.index)}`;
    // The router may scroll on arrival after this effect, and the lesson may still be streaming in: keep returning
    // to the block for a moment, and stop once it has sat at the top on two checks in a row, or as soon as the reader
    // scrolls, taps or types (never pull them back from where they went). The marker says when it is settled.
    const timers: ReturnType<typeof setTimeout>[] = [];
    let frame = 0;
    let atTop = 0;
    const inputs = ["wheel", "touchstart", "pointerdown", "keydown"] as const;
    const finish = () => {
      cancelAnimationFrame(frame);
      timers.forEach(clearTimeout);
      inputs.forEach((t) => window.removeEventListener(t, finish, true));
      marker.current?.setAttribute("data-place", "settled");
    };
    const go = () => {
      const el = document.getElementById(id);
      if (!el) return;
      try {
        window.sessionStorage.removeItem(KEY);
      } catch {
        // see above
      }
      if (Math.abs(el.getBoundingClientRect().top - 80) > 4) {
        atTop = 0;
        el.scrollIntoView({ block: "start" });
      } else if (++atTop >= 2) {
        finish();
      }
    };
    marker.current?.setAttribute("data-place", "returning");
    inputs.forEach((t) => window.addEventListener(t, finish, { capture: true, passive: true }));
    frame = requestAnimationFrame(go);
    for (const ms of [150, 350, 700, 1200]) timers.push(setTimeout(go, ms));
    timers.push(setTimeout(finish, 2000));
    return finish;
  }, [lessonId, signatures]);

  // Listen on the document: the form's DOM node is replaced after each switch, while this component is kept.
  useEffect(() => {
    const onSubmit = (e: Event) => {
      if (e.target !== marker.current?.closest("form")) return;
      const blocks = Array.from(document.querySelectorAll<HTMLElement>("[data-block]"));
      // Blocks scroll to 80 px (their scroll margin); allow for sub-pixel layout.
      const top = blocks.filter((b) => b.getBoundingClientRect().top <= 84).at(-1);
      const index = top ? Number(top.id.slice(1)) : NaN;
      if (!Number.isInteger(index)) return;
      const note: Note = { index, ...current.current, at: Date.now() };
      try {
        window.sessionStorage.setItem(KEY, JSON.stringify(note));
      } catch {
        // see above
      }
    };
    document.addEventListener("submit", onSubmit, true);
    return () => document.removeEventListener("submit", onSubmit, true);
  }, []);

  return <span ref={marker} hidden />;
}
