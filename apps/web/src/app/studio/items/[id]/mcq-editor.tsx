"use client";

// Single-best-answer question editor (P08.S1). Option IDs are stable: they are never renumbered when options are
// added, removed or reordered, so attempts, distractor notes and corrections keep pointing at the same option.
import type { Block } from "@/app/actions/studio";
import { LessonBlocks } from "@/components/lesson-blocks";
import { BlockEditor, normaliseBlocks } from "./block-editor";

type Option = { id: string; blocks: Block[] };
type Explanation = { correct: Block[]; distractors: Record<string, string>; worked_steps: Block[] };
type Metadata = {
  difficulty?: "easy" | "medium" | "hard" | null;
  estimated_seconds?: number | null;
  cognitive_demand?: "recall" | "understand" | "apply" | "analyse" | null;
  misconceptions?: string[];
};
type PastPaper = { board: string; year: number; paper?: string | null; authorisation_ref: string };
export type McqBody = {
  stem: Block[];
  options: Option[];
  correct_option_id: string | null;
  marks: number;
  shuffle_options: boolean;
  explanation: Explanation;
  metadata: Metadata;
  origin: "original_practice" | "authorised_past_paper";
  past_paper: PastPaper | null;
  language: "en" | "ur";
};

export function asMcq(body: Record<string, unknown>): McqBody {
  const b = body as Partial<McqBody>;
  return {
    stem: b.stem ?? [],
    options: b.options ?? [],
    correct_option_id: b.correct_option_id ?? null,
    marks: b.marks ?? 1,
    shuffle_options: b.shuffle_options ?? true,
    explanation: { correct: [], distractors: {}, worked_steps: [], ...(b.explanation ?? {}) },
    metadata: b.metadata ?? {},
    origin: b.origin ?? "original_practice",
    past_paper: b.past_paper ?? null,
    language: b.language ?? "en",
  };
}

/** Shape the editor state into the API schema (drop empty list items, empty notes, unset optional fields). */
export function normaliseMcq(body: Record<string, unknown>): Record<string, unknown> {
  const q = asMcq(body);
  const distractors = Object.fromEntries(
    Object.entries(q.explanation.distractors).filter(([id, note]) => note.trim() && q.options.some((o) => o.id === id)),
  );
  const metadata = Object.fromEntries(Object.entries(q.metadata).filter(([, v]) => v !== null && v !== undefined));
  const out: Record<string, unknown> = {
    stem: normaliseBlocks(q.stem),
    options: q.options.map((o) => ({ id: o.id, blocks: normaliseBlocks(o.blocks) })),
    correct_option_id: q.correct_option_id,
    marks: q.marks,
    shuffle_options: q.shuffle_options,
    explanation: {
      correct: normaliseBlocks(q.explanation.correct),
      distractors,
      worked_steps: normaliseBlocks(q.explanation.worked_steps),
    },
    metadata,
    origin: q.origin,
    language: q.language,
  };
  if (q.origin === "authorised_past_paper" && q.past_paper) out.past_paper = q.past_paper;
  return out;
}

function nextOptionId(options: Option[]): string {
  for (let n = 1; ; n++) if (!options.some((o) => o.id === `o${n}`)) return `o${n}`;
}

const input = "w-full rounded-lg border border-border bg-surface px-3 py-2";
const small = "rounded-md border border-border px-2 py-1 text-xs hover:border-accent disabled:opacity-40";

export function McqEditor({ body, onChange }: { body: Record<string, unknown>; onChange: (b: Record<string, unknown>) => void }) {
  const q = asMcq(body);
  const set = (patch: Partial<McqBody>) => onChange({ ...q, ...patch });
  const setOption = (i: number, blocks: Block[]) => set({ options: q.options.map((o, j) => (j === i ? { ...o, blocks } : o)) });
  const removeOption = (i: number) => {
    const removed = q.options[i];
    const distractors = { ...q.explanation.distractors };
    delete distractors[removed.id];
    set({
      options: q.options.filter((_, j) => j !== i),
      correct_option_id: q.correct_option_id === removed.id ? null : q.correct_option_id,
      explanation: { ...q.explanation, distractors },
    });
  };
  const move = (i: number, d: -1 | 1) => {
    const next = [...q.options];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    set({ options: next });
  };

  return (
    <div className="space-y-6">
      <section className="space-y-2" aria-labelledby="stem-h">
        <h2 id="stem-h" className="font-medium">
          Question stem
        </h2>
        <BlockEditor blocks={q.stem} onChange={(stem) => set({ stem })} />
      </section>

      <section className="space-y-3" aria-labelledby="options-h">
        <div className="flex items-center justify-between gap-2">
          <h2 id="options-h" className="font-medium">
            Options
          </h2>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={q.shuffle_options} onChange={(e) => set({ shuffle_options: e.target.checked })} />
            Shuffle options for learners
          </label>
        </div>
        <fieldset className="space-y-3">
          <legend className="sr-only">Options and correct answer</legend>
          {q.options.map((o, i) => (
            <div key={o.id} className={`space-y-2 rounded-xl border p-3 ${q.correct_option_id === o.id ? "border-ok bg-ok-soft" : "border-border bg-surface"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input type="radio" name="correct" checked={q.correct_option_id === o.id} onChange={() => set({ correct_option_id: o.id })} />
                  Option {o.id} {q.correct_option_id === o.id ? "(correct answer)" : ""}
                </label>
                <div className="flex gap-1">
                  <button type="button" className={small} onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move option ${o.id} up`}>
                    ↑
                  </button>
                  <button type="button" className={small} onClick={() => move(i, 1)} disabled={i === q.options.length - 1} aria-label={`Move option ${o.id} down`}>
                    ↓
                  </button>
                  <button type="button" className={small} onClick={() => removeOption(i)} aria-label={`Remove option ${o.id}`}>
                    Remove
                  </button>
                </div>
              </div>
              <BlockEditor blocks={o.blocks} onChange={(blocks) => setOption(i, blocks)} />
              {q.correct_option_id !== o.id && (
                <label className="block space-y-1 text-sm">
                  <span className="text-muted">Why a learner might choose {o.id}, and why it is wrong</span>
                  <textarea
                    value={q.explanation.distractors[o.id] ?? ""}
                    onChange={(e) => set({ explanation: { ...q.explanation, distractors: { ...q.explanation.distractors, [o.id]: e.target.value } } })}
                    rows={2}
                    maxLength={2000}
                    className={input}
                  />
                </label>
              )}
            </div>
          ))}
        </fieldset>
        {q.options.length < 6 && (
          <button type="button" className={small} onClick={() => set({ options: [...q.options, { id: nextOptionId(q.options), blocks: [] }] })}>
            + Add option
          </button>
        )}
      </section>

      <section className="space-y-2" aria-labelledby="expl-h">
        <h2 id="expl-h" className="font-medium">
          Why the correct answer is correct
        </h2>
        <BlockEditor blocks={q.explanation.correct} onChange={(correct) => set({ explanation: { ...q.explanation, correct } })} />
        <h3 className="pt-2 text-sm font-medium">Worked steps (optional)</h3>
        <BlockEditor blocks={q.explanation.worked_steps} onChange={(worked_steps) => set({ explanation: { ...q.explanation, worked_steps } })} />
      </section>

      <section className="grid gap-4 sm:grid-cols-2" aria-label="Question details">
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Marks</span>
          <input type="number" min={1} max={10} value={q.marks} onChange={(e) => set({ marks: Number(e.target.value) || 1 })} className={input} />
        </label>
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Editorial difficulty</span>
          <select value={q.metadata.difficulty ?? ""} onChange={(e) => set({ metadata: { ...q.metadata, difficulty: (e.target.value || null) as Metadata["difficulty"] } })} className={input}>
            <option value="">Not set</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Estimated time (seconds)</span>
          <input
            type="number"
            min={10}
            max={1800}
            value={q.metadata.estimated_seconds ?? ""}
            onChange={(e) => set({ metadata: { ...q.metadata, estimated_seconds: e.target.value ? Number(e.target.value) : null } })}
            className={input}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Cognitive demand</span>
          <select
            value={q.metadata.cognitive_demand ?? ""}
            onChange={(e) => set({ metadata: { ...q.metadata, cognitive_demand: (e.target.value || null) as Metadata["cognitive_demand"] } })}
            className={input}
          >
            <option value="">Not set</option>
            <option value="recall">Recall</option>
            <option value="understand">Understand</option>
            <option value="apply">Apply</option>
            <option value="analyse">Analyse</option>
          </select>
        </label>
        <label className="space-y-1 text-sm sm:col-span-2">
          <span className="block font-medium">Origin</span>
          <select value={q.origin} onChange={(e) => set({ origin: e.target.value as McqBody["origin"] })} className={input}>
            <option value="original_practice">Original practice question</option>
            <option value="authorised_past_paper">Authorised past-paper question</option>
          </select>
        </label>
        {q.origin === "authorised_past_paper" && (
          <fieldset className="grid gap-3 rounded-xl border border-border p-3 sm:col-span-2 sm:grid-cols-2">
            <legend className="px-1 text-sm font-medium">Past paper</legend>
            {(
              [
                ["board", "Board", "text"],
                ["year", "Year", "number"],
                ["paper", "Paper (optional)", "text"],
                ["authorisation_ref", "Where reuse is authorised", "text"],
              ] as const
            ).map(([key, label, type]) => (
              <label key={key} className="space-y-1 text-sm">
                <span className="block text-muted">{label}</span>
                <input
                  type={type}
                  value={(q.past_paper?.[key] as string | number | undefined) ?? ""}
                  onChange={(e) =>
                    set({
                      past_paper: {
                        board: "",
                        year: new Date().getFullYear(),
                        authorisation_ref: "",
                        ...q.past_paper,
                        [key]: type === "number" ? Number(e.target.value) : e.target.value,
                      },
                    })
                  }
                  className={input}
                />
              </label>
            ))}
          </fieldset>
        )}
      </section>
    </div>
  );
}

/** Staff preview. Shows the answer key and explanations: staff-only, never a learner payload. */
export function McqPreview({ body }: { body: Record<string, unknown> }) {
  const q = asMcq(body);
  return (
    <div className="space-y-4">
      <LessonBlocks blocks={q.stem} headingOffset={1} />
      <ol className="space-y-2" aria-label="Options">
        {q.options.map((o) => (
          <li key={o.id} className={`rounded-lg border px-3 py-2 ${o.id === q.correct_option_id ? "border-ok bg-ok-soft" : "border-border"}`}>
            <span className="mr-2 font-mono text-xs text-muted">{o.id}</span>
            {o.id === q.correct_option_id && <span className="mr-2 text-xs font-semibold text-ok">KEY</span>}
            <LessonBlocks blocks={o.blocks} headingOffset={2} />
            {q.explanation.distractors[o.id] && <p className="mt-1 text-sm text-muted">{q.explanation.distractors[o.id]}</p>}
          </li>
        ))}
      </ol>
      <div className="rounded-lg border border-border p-3">
        <p className="text-sm font-semibold">Explanation</p>
        <LessonBlocks blocks={q.explanation.correct} headingOffset={2} />
        {q.explanation.worked_steps.length > 0 && <LessonBlocks blocks={q.explanation.worked_steps} headingOffset={2} />}
      </div>
      <p className="text-xs text-muted">
        {q.marks} mark{q.marks === 1 ? "" : "s"} · {q.shuffle_options ? "options shuffled" : "fixed option order"} ·{" "}
        {q.origin === "authorised_past_paper" ? `past paper${q.past_paper ? ` (${q.past_paper.board} ${q.past_paper.year})` : ""}` : "original practice question"}
      </p>
    </div>
  );
}

/** Labelled plain-text sections used to compare two versions in the conflict panel. */
export function mcqSections(body: Record<string, unknown>): { label: string; text: string }[] {
  const q = asMcq(body);
  const t = (bl: Block[]) => JSON.stringify(bl);
  return [
    { label: "Stem", text: t(q.stem) },
    ...q.options.map((o) => ({ label: `Option ${o.id}`, text: t(o.blocks) })),
    { label: "Correct answer", text: String(q.correct_option_id) },
    { label: "Explanation", text: t(q.explanation.correct) + JSON.stringify(q.explanation.distractors) },
  ];
}
