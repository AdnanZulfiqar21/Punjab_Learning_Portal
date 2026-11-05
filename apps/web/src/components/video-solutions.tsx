import { Icon } from "@/components/icons";
import { MathText } from "@/components/math-text";
import { Notice } from "@/components/ui";
import { typesetMath } from "@/lib/typeset";

/** A solved book question as its lesson carries it (SOLVED-QUESTION-01). */
export type SolvedQuestion = { type: string; ref?: unknown; prompt?: unknown };

/** The solved book questions of a lesson: its self-checks that carry a printed question number. */
export function solvedQuestions(blocks: readonly { type: string; [key: string]: unknown }[] | null | undefined): SolvedQuestion[] {
  return (blocks ?? []).filter((b) => b.type === "checkpoint" && typeof b.ref === "string") as SolvedQuestion[];
}

/**
 * VIDEO-SOLUTION-01 (owner, 2026-11-05): the "Video Solution" view of a Mathematics exercise question. Each part of the
 * question gets its own video solution; until one is added, the part says "Video not available yet". No player is shown
 * without a video.
 */
export function VideoSolutions({ questions }: { questions: SolvedQuestion[] }) {
  const math = typesetMath(questions.map((q) => q.prompt));
  return (
    <section aria-labelledby="video-solutions" className="space-y-4">
      <h2 id="video-solutions" className="sr-only">
        Video solutions
      </h2>
      <Notice title="Video solutions are not available yet">
        Every part of this question will get its own video solution, explained step by step. Until its video is added, the worked solution is in
        the English and Roman Urdu views.
      </Notice>
      <ol className="space-y-3">
        {questions.map((q, i) => (
          <li key={i} className="rounded-card border border-border bg-surface px-4 py-4 shadow-sm" data-ref={typeof q.ref === "string" ? q.ref : undefined}>
            {typeof q.ref === "string" && <p className="text-xs font-semibold tracking-wide text-accent-strong uppercase">Question {q.ref}</p>}
            <p className="mt-1 whitespace-pre-wrap">
              <MathText text={typeof q.prompt === "string" ? q.prompt : ""} html={math} />
            </p>
            <p className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-surface-muted px-3 py-1 text-sm font-medium text-muted" role="status">
              <Icon name="play" size={14} />
              Video not available yet
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
