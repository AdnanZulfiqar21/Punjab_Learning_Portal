"use client";

import type { Block, SourceRef } from "@/app/actions/studio";

const input = "w-full rounded-lg border border-border bg-surface px-3 py-2";
const small = "rounded-md border border-border px-2 py-1 text-xs hover:border-accent disabled:opacity-40";

export const BLOCK_TYPES: { type: string; label: string; make: () => Block }[] = [
  { type: "heading", label: "Heading", make: () => ({ type: "heading", level: 2, text: "" }) },
  { type: "paragraph", label: "Paragraph", make: () => ({ type: "paragraph", text: "" }) },
  { type: "list", label: "List", make: () => ({ type: "list", ordered: false, items: [""] }) },
  { type: "callout", label: "Callout", make: () => ({ type: "callout", tone: "definition", text: "" }) },
  { type: "table", label: "Table", make: () => ({ type: "table", caption: "", header: ["", ""], rows: [["", ""]] }) },
  { type: "equation", label: "Equation", make: () => ({ type: "equation", latex: "", text_alt: "", display: true }) },
  {
    type: "checkpoint",
    label: "Checkpoint",
    make: () => ({ type: "checkpoint", mode: "question", prompt: "", options: [{ id: "a", text: "" }, { id: "b", text: "" }], answer_id: "a", explanation: "" }),
  },
];

const OPTION_IDS = "abcdef";
type CheckpointOption = { id: string; text: string };
/** Options as lines; a leading "*" marks the correct one (P07.S1.T3). */
const optionLines = (b: Block) =>
  (Array.isArray(b.options) ? (b.options as CheckpointOption[]) : []).map((o) => `${o.id === b.answer_id ? "* " : ""}${o.text}`).join("\n");
function parseOptions(text: string): { options: CheckpointOption[]; answer_id: string | undefined } {
  const rows = text.split("\n").slice(0, 6);
  const options = rows.map((line, i) => ({ id: OPTION_IDS[i], text: line.replace(/^\s*\*\s*/, "") }));
  const marked = rows.findIndex((line) => /^\s*\*/.test(line));
  return { options, answer_id: marked >= 0 ? OPTION_IDS[marked] : undefined };
}

const s = (v: unknown) => (typeof v === "string" ? v : "");
const lines = (v: unknown) => (Array.isArray(v) ? v.map(s).join("\n") : "");
const cells = (row: unknown) => (Array.isArray(row) ? row.map(s).join(" | ") : "");
const splitCells = (line: string) => line.split("|").map((c) => c.trim());

export function BlockEditor({
  blocks,
  onChange,
  disabled,
}: {
  blocks: Block[];
  onChange: (blocks: Block[]) => void;
  disabled?: boolean;
}) {
  const update = (i: number, patch: Partial<Block>) => onChange(blocks.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  const move = (i: number, d: -1 | 1) => {
    const next = [...blocks];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onChange(next);
  };
  return (
    <div className="space-y-3">
      {blocks.length === 0 && <p className="text-sm text-muted">No blocks yet. Add the first one below.</p>}
      {blocks.map((b, i) => (
        <fieldset key={i} className="space-y-2 rounded-xl border border-border bg-surface p-3" disabled={disabled}>
          <div className="flex items-center justify-between gap-2">
            <legend className="text-xs font-semibold tracking-wide text-muted uppercase">
              {i + 1}. {BLOCK_TYPES.find((t) => t.type === b.type)?.label ?? b.type}
            </legend>
            <div className="flex gap-1">
              <button type="button" className={small} onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move block ${i + 1} up`}>
                ↑
              </button>
              <button type="button" className={small} onClick={() => move(i, 1)} disabled={i === blocks.length - 1} aria-label={`Move block ${i + 1} down`}>
                ↓
              </button>
              <button type="button" className={small} onClick={() => onChange(blocks.filter((_, j) => j !== i))} aria-label={`Remove block ${i + 1}`}>
                Remove
              </button>
            </div>
          </div>
          <Fields block={b} index={i} update={(p) => update(i, p)} />
        </fieldset>
      ))}
      {!disabled && (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Add a block">
          <span className="text-sm text-muted">Add:</span>
          {BLOCK_TYPES.map((t) => (
            <button key={t.type} type="button" className={small} onClick={() => onChange([...blocks, t.make()])}>
              + {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Fields({ block: b, index, update }: { block: Block; index: number; update: (p: Partial<Block>) => void }) {
  const id = (f: string) => `b${index}-${f}`;
  switch (b.type) {
    case "heading":
      return (
        <div className="flex gap-2">
          <select aria-label="Heading level" value={Number(b.level) || 2} onChange={(e) => update({ level: Number(e.target.value) })} className="rounded-lg border border-border bg-surface px-2">
            <option value={2}>H2</option>
            <option value={3}>H3</option>
          </select>
          <input aria-label="Heading text" value={s(b.text)} onChange={(e) => update({ text: e.target.value })} className={input} maxLength={300} />
        </div>
      );
    case "paragraph":
      return <textarea aria-label="Paragraph text" value={s(b.text)} onChange={(e) => update({ text: e.target.value })} className={input} rows={4} maxLength={5000} />;
    case "list":
      return (
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!b.ordered} onChange={(e) => update({ ordered: e.target.checked })} />
            Numbered
          </label>
          <label htmlFor={id("items")} className="block text-sm text-muted">
            One item per line
          </label>
          <textarea id={id("items")} value={lines(b.items)} onChange={(e) => update({ items: e.target.value.split("\n") })} className={input} rows={4} />
        </div>
      );
    case "callout":
      return (
        <div className="space-y-2">
          <div className="flex gap-2">
            <select aria-label="Callout type" value={s(b.tone) || "note"} onChange={(e) => update({ tone: e.target.value })} className="rounded-lg border border-border bg-surface px-2">
              <option value="definition">Definition</option>
              <option value="note">Note</option>
              <option value="tip">Tip</option>
              <option value="warning">Warning</option>
            </select>
            <input aria-label="Callout title (optional)" placeholder="Title (optional)" value={s(b.title)} onChange={(e) => update({ title: e.target.value || undefined })} className={input} maxLength={300} />
          </div>
          <textarea aria-label="Callout text" value={s(b.text)} onChange={(e) => update({ text: e.target.value })} className={input} rows={3} maxLength={5000} />
        </div>
      );
    case "table":
      return (
        <div className="space-y-2">
          <input aria-label="Table caption" placeholder="Caption" value={s(b.caption)} onChange={(e) => update({ caption: e.target.value })} className={input} maxLength={300} />
          <label htmlFor={id("header")} className="block text-sm text-muted">
            Header cells, separated by |
          </label>
          <input id={id("header")} value={cells(b.header)} onChange={(e) => update({ header: splitCells(e.target.value) })} className={input} />
          <label htmlFor={id("rows")} className="block text-sm text-muted">
            One row per line, cells separated by |
          </label>
          <textarea
            id={id("rows")}
            value={Array.isArray(b.rows) ? (b.rows as unknown[]).map(cells).join("\n") : ""}
            onChange={(e) => update({ rows: e.target.value.split("\n").map(splitCells) })}
            className={`${input} font-mono text-sm`}
            rows={4}
          />
        </div>
      );
    case "equation":
      return (
        <div className="space-y-2">
          <input aria-label="LaTeX" placeholder="LaTeX, e.g. v = u + at" value={s(b.latex)} onChange={(e) => update({ latex: e.target.value })} className={`${input} font-mono`} maxLength={2000} />
          <input aria-label="Text equivalent" placeholder="Text equivalent, e.g. v equals u plus a t" value={s(b.text_alt)} onChange={(e) => update({ text_alt: e.target.value })} className={input} maxLength={1000} />
          <p className="text-xs text-muted">Publishing an equation needs a reviewed static rendering until the equation renderer ships.</p>
        </div>
      );
    case "checkpoint": {
      const question = b.mode !== "self_check";
      return (
        <div className="space-y-2">
          <select
            aria-label="Checkpoint type"
            value={question ? "question" : "self_check"}
            onChange={(e) =>
              update(
                e.target.value === "question"
                  ? { mode: "question", options: [{ id: "a", text: "" }, { id: "b", text: "" }], answer_id: "a" }
                  : { mode: "self_check", options: [], answer_id: undefined },
              )
            }
            className="rounded-lg border border-border bg-surface px-2 py-1"
          >
            <option value="question">Question with a reason</option>
            <option value="self_check">Self-check</option>
          </select>
          <textarea aria-label="Checkpoint prompt" placeholder="Prompt" value={s(b.prompt)} onChange={(e) => update({ prompt: e.target.value })} className={input} rows={2} maxLength={5000} />
          {question && (
            <>
              <label htmlFor={id("options")} className="block text-sm text-muted">
                Options, one per line (2 to 6); start the correct one with *
              </label>
              <textarea id={id("options")} value={optionLines(b)} onChange={(e) => update(parseOptions(e.target.value))} className={input} rows={4} />
            </>
          )}
          <textarea
            aria-label={question ? "Why the correct option is correct" : "What a good answer contains"}
            placeholder={question ? "Why the correct option is correct (shown after answering)" : "What a good answer contains (shown when revealed)"}
            value={s(b.explanation)}
            onChange={(e) => update({ explanation: e.target.value })}
            className={input}
            rows={3}
            maxLength={5000}
          />
          <p className="text-xs text-muted">Checkpoints are self-checks: answers aren&apos;t stored or scored. Don&apos;t reuse question-bank items here.</p>
        </div>
      );
    }
    default:
      return <p className="text-sm text-muted">This block type can&apos;t be edited here.</p>;
  }
}

/** Clean editor input into the API's block schema: drop empty list items/rows and empty optional fields. */
export function normaliseBlocks(blocks: Block[]): Block[] {
  return blocks.map((b) => {
    if (b.type === "list") return { ...b, items: (b.items as string[]).map((x) => x.trim()).filter(Boolean) };
    if (b.type === "table") {
      return { ...b, rows: (b.rows as string[][]).filter((r) => r.some((c) => c.trim())) };
    }
    if (b.type === "checkpoint") {
      if (b.mode === "self_check") return { type: "checkpoint", mode: "self_check", prompt: b.prompt, explanation: b.explanation };
      const options = ((b.options as CheckpointOption[]) ?? []).filter((o) => o.text.trim());
      return { ...b, options, answer_id: options.some((o) => o.id === b.answer_id) ? b.answer_id : undefined };
    }
    if (b.type === "callout" && !s(b.title).trim()) {
      const rest: Block = { ...b };
      delete rest.title;
      return rest;
    }
    return b;
  });
}

export function SourceRefsEditor({
  refs,
  onChange,
  sourceId,
  sourceLabel,
  pdfPages,
  chapterRange,
  disabled,
}: {
  refs: SourceRef[];
  onChange: (refs: SourceRef[]) => void;
  sourceId: string;
  sourceLabel: string;
  pdfPages: number;
  chapterRange: [number | null, number | null];
  disabled?: boolean;
}) {
  const update = (i: number, patch: Partial<SourceRef>) => onChange(refs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const [start, end] = chapterRange;
  return (
    <fieldset className="space-y-2" disabled={disabled}>
      <legend className="font-medium">Source pages</legend>
      <p className="text-sm text-muted">
        {sourceLabel} · PDF pages 1–{pdfPages}
        {start && end ? ` · this chapter is PDF ${start}–${end}` : ""}. Reference pages; never paste textbook text.
      </p>
      {refs.map((r, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <label className="text-sm">
            PDF from{" "}
            <input type="number" min={1} max={pdfPages} value={r.pdf_from} onChange={(e) => update(i, { pdf_from: Number(e.target.value) })} className="w-24 rounded-lg border border-border bg-surface px-2 py-1" />
          </label>
          <label className="text-sm">
            to{" "}
            <input type="number" min={1} max={pdfPages} value={r.pdf_to} onChange={(e) => update(i, { pdf_to: Number(e.target.value) })} className="w-24 rounded-lg border border-border bg-surface px-2 py-1" />
          </label>
          <input aria-label={`Note for reference ${i + 1}`} placeholder="Note (optional)" value={r.note ?? ""} onChange={(e) => update(i, { note: e.target.value || null })} className="min-w-40 flex-1 rounded-lg border border-border bg-surface px-2 py-1 text-sm" maxLength={300} />
          <button type="button" className={small} onClick={() => onChange(refs.filter((_, j) => j !== i))}>
            Remove
          </button>
        </div>
      ))}
      {!disabled && (
        <button
          type="button"
          className={small}
          onClick={() => onChange([...refs, { source_document_id: sourceId, pdf_from: start ?? 1, pdf_to: start ?? 1, note: null }])}
        >
          + Add page reference
        </button>
      )}
    </fieldset>
  );
}
