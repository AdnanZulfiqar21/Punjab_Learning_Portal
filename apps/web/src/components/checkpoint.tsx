"use client";

// A formative checkpoint inside a lesson (P07.S1.T3). Self-check only: nothing is sent, stored or scored.
import { type ReactNode, useId, useState } from "react";

type Option = { id: string; text: string };

export function Checkpoint({
  mode,
  prompt,
  options,
  answerId,
  explanation,
  answerFigure,
  revealLabel = "Show what a good answer contains",
}: {
  mode: "question" | "self_check";
  prompt: string;
  options: Option[];
  answerId: string | null;
  explanation: string;
  /** ANSWER-FIGURE-01: the drawn answer, shown with the explanation once revealed, never before. */
  answerFigure?: ReactNode;
  /** BOOK-EXERCISES-01: the self-check button's words ("Show answer" / "Answer dekhein" on a book exercise). */
  revealLabel?: string;
}) {
  const [chosen, setChosen] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const name = useId();
  const done = mode === "question" ? chosen !== null : revealed;
  return (
    <aside aria-label="Check your understanding" className="space-y-3 rounded-xl border border-accent/40 bg-accent-soft p-4">
      <p className="text-sm font-semibold">Check your understanding</p>
      {/* Prompts and answers keep their line breaks and indentation: book exercises quote and answer with programs. */}
      <p className="whitespace-pre-wrap">{prompt}</p>
      {mode === "question" ? (
        <fieldset className="space-y-2" disabled={chosen !== null}>
          <legend className="sr-only">{prompt}</legend>
          {options.map((o) => {
            const state = chosen === null ? "" : o.id === answerId ? "border-ok" : o.id === chosen ? "border-warn" : "border-border";
            return (
              <label key={o.id} className={`flex items-start gap-2 rounded-lg border bg-surface px-3 py-2 ${state || "border-border"}`}>
                <input type="radio" name={name} value={o.id} checked={chosen === o.id} onChange={() => setChosen(o.id)} className="mt-1" />
                <span>
                  {o.text}
                  {chosen !== null && o.id === answerId && <span className="ml-2 text-sm font-medium">✓ Correct</span>}
                </span>
              </label>
            );
          })}
        </fieldset>
      ) : (
        !revealed && (
          <button type="button" onClick={() => setRevealed(true)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent">
            {revealLabel}
          </button>
        )
      )}
      {done && (
        <p role="status" className="text-sm">
          {mode === "question" && (chosen === answerId ? "Right. " : "Not quite. ")}
          <span className="whitespace-pre-wrap">{explanation}</span>
        </p>
      )}
      {done && answerFigure}
    </aside>
  );
}
