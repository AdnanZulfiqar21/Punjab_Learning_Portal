import { Checkpoint } from "@/components/checkpoint";

// Renders content blocks (schema v1, roadmap §5.4). Unknown block types never crash the page: they show an explicit
// "update required" notice, as the renderer contract requires.
type Block = { type: string; [key: string]: unknown };

const str = (v: unknown) => (typeof v === "string" ? v : "");
const strs = (v: unknown) => (Array.isArray(v) ? v.map(str) : []);

const CALLOUT_STYLE: Record<string, string> = {
  definition: "border-accent bg-accent-soft",
  note: "border-border bg-surface-muted",
  tip: "border-ok bg-ok-soft",
  warning: "border-warn bg-warn-soft",
};

/** `headingOffset` shifts block headings down so they nest under the page's own headings (level 2 → h{2+offset}). */
export function LessonBlocks({ blocks, headingOffset = 0 }: { blocks: Block[]; headingOffset?: number }) {
  return (
    <div className="space-y-4 leading-relaxed">
      {blocks.map((b, i) => (
        <BlockView key={i} block={b} headingOffset={headingOffset} />
      ))}
    </div>
  );
}

function BlockView({ block: b, headingOffset }: { block: Block; headingOffset: number }) {
  switch (b.type) {
    case "heading": {
      const level = Math.min(6, (b.level === 3 ? 3 : 2) + headingOffset);
      const Tag = `h${level}` as "h2" | "h3" | "h4" | "h5" | "h6";
      return <Tag className={b.level === 3 ? "text-lg font-semibold" : "text-xl font-semibold tracking-tight"}>{str(b.text)}</Tag>;
    }
    case "paragraph":
      return <p className="whitespace-pre-line">{str(b.text)}</p>;
    case "list": {
      const items = strs(b.items).map((t, i) => <li key={i}>{t}</li>);
      return b.ordered ? (
        <ol className="list-decimal space-y-1 pl-6">{items}</ol>
      ) : (
        <ul className="list-disc space-y-1 pl-6">{items}</ul>
      );
    }
    case "callout": {
      const tone = str(b.tone) || "note";
      return (
        <aside className={`rounded-lg border-l-4 px-4 py-3 ${CALLOUT_STYLE[tone] ?? CALLOUT_STYLE.note}`}>
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">{tone}</p>
          {str(b.title) && <p className="font-semibold">{str(b.title)}</p>}
          <p className="whitespace-pre-line">{str(b.text)}</p>
        </aside>
      );
    }
    case "table": {
      const header = strs(b.header);
      const rows = Array.isArray(b.rows) ? (b.rows as unknown[]).map(strs) : [];
      return (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="mb-2 text-left font-medium">{str(b.caption)}</caption>
            <thead>
              <tr>
                {header.map((h, i) => (
                  <th key={i} scope="col" className="border border-border bg-surface-muted px-3 py-2 text-left">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j} className="border border-border px-3 py-2">
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    case "checkpoint":
      return (
        <Checkpoint
          mode={b.mode === "self_check" ? "self_check" : "question"}
          prompt={str(b.prompt)}
          options={Array.isArray(b.options) ? (b.options as { id: string; text: string }[]) : []}
          answerId={typeof b.answer_id === "string" ? b.answer_id : null}
          explanation={str(b.explanation)}
        />
      );
    case "equation":
      // No typeset renderer ships yet (§5.4: equations need a reviewed fallback before publication). Show the text
      // equivalent, with the source LaTeX for staff checking.
      return (
        <figure className="rounded-lg border border-border bg-surface px-4 py-3">
          <p>{str(b.text_alt)}</p>
          <figcaption className="mt-1 font-mono text-xs text-muted">{str(b.latex)}</figcaption>
        </figure>
      );
    default:
      return (
        <p role="note" className="rounded-lg border border-warn bg-warn-soft px-4 py-3 text-sm">
          This part of the lesson needs a newer version of the app to display.
        </p>
      );
  }
}
