// PREMIUM-LOOK-01: Motion Primitives "Text Effect" pattern in CSS only (no animation library, keeps the JS budget):
// words rise in with a soft blur, one after another. Screen readers get the sentence once.
import type { CSSProperties } from "react";

export function TextEffect({ text, className, wordClassName = "", delay = 0 }: { text: string; className?: string; wordClassName?: string; delay?: number }) {
  const words = text.split(" ");
  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      {words.map((w, i) => (
        <span
          key={`${w}-${i}`}
          aria-hidden
          className={`text-rise inline-block whitespace-pre ${wordClassName}`}
          style={{ "--rise-delay": `${delay + i * 0.06}s` } as CSSProperties}
        >
          {w}
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </span>
  );
}
