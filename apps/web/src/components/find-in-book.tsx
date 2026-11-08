"use client";

// MCQ-BOOK-LINK-01 (owner, 2026-11-08: "ake button banao jo student ko seedha book ka ous heesy pr la jaye jaha pr ya mcq
// hy or ous hessay ko highlight kr do"): a practice question's "See in book" opens its Learn topic with `?find=<the
// book's words>`. This finds those words in the lesson text, marks them and scrolls them to the middle of the screen.
// Words that are not on the page (a changed lesson) leave the page as it is.
import { useEffect } from "react";

const squash = (s: string) => s.replace(/\s+/g, " ");

export function FindInBook({ text }: { text: string }) {
  useEffect(() => {
    const root = document.querySelector("[data-lesson-body]");
    const wanted = squash(text).trim();
    if (!root || !wanted) return;
    // The page's text as one string (whitespace squashed), with where each piece came from.
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const pieces: { node: Text; start: number; map: number[] }[] = [];
    let all = "";
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const node = n as Text;
      const raw = node.data;
      const map: number[] = [];
      let out = "";
      for (let i = 0; i < raw.length; i++) {
        const ch = /\s/.test(raw[i]) ? " " : raw[i];
        if (ch === " " && (all + out).endsWith(" ")) continue;
        out += ch;
        map.push(i);
      }
      pieces.push({ node, start: all.length, map });
      all += out;
    }
    const at = all.indexOf(wanted);
    if (at < 0) return;
    const end = at + wanted.length;
    const marks: HTMLElement[] = [];
    for (const p of pieces) {
      const from = Math.max(at, p.start) - p.start;
      const to = Math.min(end, p.start + p.map.length) - p.start;
      if (to <= from) continue;
      const range = document.createRange();
      range.setStart(p.node, p.map[from]);
      range.setEnd(p.node, p.map[to - 1] + 1);
      const mark = document.createElement("mark");
      mark.className = "find-in-book";
      range.surroundContents(mark);
      marks.push(mark);
    }
    if (!marks.length) return;
    marks[0].setAttribute("tabindex", "-1");
    // After the page has restored any saved place, bring the passage into view.
    const t = window.setTimeout(() => {
      marks[0].scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      marks[0].focus({ preventScroll: true });
    }, 350);
    return () => window.clearTimeout(t);
  }, [text]);
  return null;
}
