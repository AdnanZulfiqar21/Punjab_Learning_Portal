"use client";

// A formative checkpoint inside a lesson (P07.S1.T3). Self-check only: nothing is sent, stored or scored.
import Link from "next/link";
import { type ReactNode, useId, useState } from "react";
import { SOLVED_LABELS_EN, type SolvedLabels } from "@/lib/solved-labels";

type Option = { id: string; text: string };


export function Checkpoint({
  mode,
  prompt,
  promptView,
  options,
  answerId,
  explanation,
  explanationView,
  answerFigure,
  revealLabel = "Show what a good answer contains",
  qref,
  steps,
  finalAnswer,
  labels = SOLVED_LABELS_EN,
  bookHref,
  number,
}: {
  mode: "question" | "self_check";
  prompt: string;
  /** How the prompt is shown (e.g. with its formulas typeset); the plain prompt names the question for screen readers. */
  promptView?: ReactNode;
  options: Option[];
  answerId: string | null;
  explanation: string;
  explanationView?: ReactNode;
  /** ANSWER-FIGURE-01: the drawn answer, shown with the explanation once revealed, never before. */
  answerFigure?: ReactNode;
  /** BOOK-EXERCISES-01: the self-check button's words ("Show answer" / "Answer dekhein" on a book exercise). */
  revealLabel?: string;
  /** SOLVED-QUESTION-01: the printed question number ("3(ii)"). */
  qref?: string;
  /** SOLVED-QUESTION-01: the numbered working, shown with the revealed answer. */
  steps?: ReactNode[];
  /** SOLVED-QUESTION-01: the answer, set apart from the working. */
  finalAnswer?: ReactNode;
  labels?: SolvedLabels;
  /** MCQ-BOOK-LINK-01: opens the book passage this question comes from, highlighted. */
  bookHref?: string;
  /** QUESTION-NUMBER-01: the question's printed number, drawn apart from its words (`promptView` then has the words). */
  number?: string;
}) {
  const [chosen, setChosen] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const name = useId();
  const panelId = useId();
  const done = mode === "question" ? chosen !== null : revealed;
  const solved = mode === "self_check" && (Boolean(steps?.length) || finalAnswer !== undefined);
  const promptLine = number ? (
    <p className="flex items-start gap-3">
      <span
        className="question-number mt-px inline-flex h-8 min-w-8 shrink-0 items-center justify-center rounded-full bg-accent px-2.5 text-sm font-bold whitespace-nowrap text-white tabular-nums shadow-sm"
      >
        <span className="sr-only">{`${labels.question} `}</span>
        {number}
      </span>
      <span className="min-w-0 flex-1 pt-1 whitespace-pre-wrap">{promptView ?? prompt}</span>
    </p>
  ) : (
    <p className="whitespace-pre-wrap">{promptView ?? prompt}</p>
  );
  if (solved) {
    // A book question solved step by step: the question, then (on demand) how to think about it, the numbered working
    // and the final answer, each set apart so a student can tell the question, the steps and the answer at a glance.
    return (
      <article aria-label={qref ? `${labels.question} ${qref}` : prompt} className="solved-question overflow-hidden rounded-xl border border-accent/40 bg-surface shadow-sm" data-ref={qref}>
        <div className="space-y-2 bg-accent-soft px-4 py-3">
          {qref && <p className="text-xs font-semibold tracking-wide text-accent-strong uppercase">{`${labels.question} ${qref}`}</p>}
          {promptLine}
          <button
            type="button"
            aria-expanded={revealed}
            aria-controls={panelId}
            onClick={() => setRevealed((r) => !r)}
            className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent"
          >
            {revealed ? labels.hide : revealLabel}
          </button>
        </div>
        {revealed && (
          <div id={panelId} className="space-y-4 px-4 py-4">
            {explanation && (
              <div className="rounded-lg border border-border bg-surface-muted px-3 py-2">
                <p className="text-xs font-semibold tracking-wide text-muted uppercase">{labels.think}</p>
                <p className="mt-1 whitespace-pre-wrap">{explanationView ?? explanation}</p>
              </div>
            )}
            {steps && steps.length > 0 && (
              <ol className="space-y-3">
                {steps.map((s, i) => (
                  <li key={i} className="solved-step flex gap-3">
                    <span aria-hidden="true" className="mt-0.5 inline-grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent-strong">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1 whitespace-pre-line">
                      <span className="sr-only">{`${labels.step} ${i + 1}: `}</span>
                      {s}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            {answerFigure}
            {finalAnswer && (
              <div className="rounded-lg border-2 border-ok bg-ok-soft px-4 py-3">
                <p className="text-xs font-semibold tracking-wide text-ok uppercase">{labels.answer}</p>
                <div className="mt-1 font-semibold whitespace-pre-line">{finalAnswer}</div>
              </div>
            )}
          </div>
        )}
      </article>
    );
  }
  return (
    <aside aria-label="Check your understanding" className="space-y-3 rounded-xl border border-accent/40 bg-accent-soft p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">Check your understanding</p>
        {bookHref && (
          <Link
            href={bookHref}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-accent/40 bg-surface px-3 text-sm font-semibold text-accent transition-colors hover:bg-accent hover:text-white focus-visible:outline-2 focus-visible:outline-accent"
          >
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 7v14" />
              <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
            </svg>
            {labels.book}
          </Link>
        )}
      </div>
      {/* Prompts and answers keep their line breaks and indentation: book exercises quote and answer with programs. */}
      {promptLine}
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
          <span className="whitespace-pre-wrap">{explanationView ?? explanation}</span>
        </p>
      )}
      {done && answerFigure}
    </aside>
  );
}
