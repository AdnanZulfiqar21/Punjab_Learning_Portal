import { Fragment, type ReactNode } from "react";
import { Checkpoint } from "@/components/checkpoint";
import { Equation } from "@/components/equation";
import { Model3DFigure } from "@/components/model3d-figure";
import { SaverImage } from "@/components/saver-image";
import { bookErrors, markLatex, markPieces } from "@/lib/book-errors";
import { leadIn, leadTerm } from "@/lib/book-style";
import { fillMerged, mergedColumns, mergeStarts, rowSpans } from "@/lib/table-merge";

// Renders content blocks (schema v1, roadmap §5.4). Web renderer version 2: comparison tables fold into cards on narrow
// screens and `model3d` blocks show a poster render with a turntable. Unknown block types never crash the page: they
// show their reviewed fallback, or an explicit "update required" notice, as the renderer contract requires.
// P01.S4.T2: equations are typeset (components/equation.tsx), and text blocks take their direction from their own text
// (`dir="auto"`), so an Urdu paragraph reads right to left while English and Roman Urdu stay left to right.
export const WEB_RENDERER_VERSION = 2;

type Block = { type: string; [key: string]: unknown };

const str = (v: unknown) => (typeof v === "string" ? v : "");
const strs = (v: unknown) => (Array.isArray(v) ? v.map(str) : []);

const CALLOUT_STYLE: Record<string, string> = {
  definition: "border-accent bg-accent-soft",
  note: "border-border bg-surface-muted",
  tip: "border-ok bg-ok-soft",
  warning: "border-warn bg-warn-soft",
  correction: "border-ok bg-ok-soft",
};
const CALLOUT_LABEL: Record<string, string> = {
  definition: "Definition",
  note: "Note",
  tip: "Tip",
  warning: "Take care",
  correction: "Book correction",
};

// READER-STYLE-01 (owner, 2026-10-27: "professional or premium"): the book's own boxes keep their printed names and a
// colour of their own, as in the textbook: Keep in Mind amber, Do You Know / For Your Information teal. A titled note is
// one of those printed boxes, so its title is its header and the generic "Note" label is dropped.
function bookBox(title: string): "keep" | "know" | null {
  if (/^keep in mind/i.test(title)) return "keep";
  if (/^(do you know|did you know|for your information|interesting information|tidbits?|point to ponder|ponder upon)/i.test(title)) return "know";
  return null;
}
const BOOK_BOX_STYLE = { keep: "border-warn bg-warn-soft", know: "border-accent bg-accent-soft" } as const;
const BOOK_BOX_HEAD = { keep: "text-warn", know: "text-accent-strong" } as const;

/** A printed "Quick Check" heading followed by its questions: one card, as the book prints it. */
function isQuickCheck(b: Block | undefined, next: Block | undefined) {
  return b?.type === "heading" && /^(quick check|self[- ]assessment)\b/i.test(str(b.text)) && next?.type === "list";
}

/** Text with the textbook's wrong passages marked in red (BOOK-CORRECTION-01). */
function Marked({ text, marks }: { text: string; marks: string[] }) {
  return (
    <>
      {markPieces(text, marks).map((p, i) =>
        p.error ? (
          <mark key={i} title="Printed in the book; see the book correction" className="rounded-sm bg-danger-soft px-0.5 text-danger">
            <Vectors text={p.text} />
          </mark>
        ) : (
          <Vectors key={i} text={p.text} />
        ),
      )}
    </>
  );
}

/** INLINE-VECTOR-01: a vector written in a sentence as a letter plus U+20D7 ("v⃗") gets its arrow drawn above the
 * letter (globals.css `.vec`): the reading font has no glyph for the combining arrow and showed an empty box. */
function Vectors({ text }: { text: string }) {
  const parts = text.split(/(\S\u20D7)/u);
  if (parts.length === 1) return <>{text}</>;
  return (
    <>
      {parts.map((part, i) =>
        i % 2 ? (
          <span key={i} className="vec" aria-label={`vector ${part[0]}`}>
            {part[0]}
          </span>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

/** Where an archived asset version's delivery copy can be fetched on this surface (P07.S1.T1): a learner lesson,
 * or the studio. Without it, diagrams show their alt text and handouts say where to get them. */
export type AssetUrl = (versionId: string) => string;
type Fallback = { text?: unknown; image_asset_id?: unknown; alt?: unknown };

/** `headingOffset` shifts block headings down so they nest under the page's own headings (level 2 → h{2+offset}). */
export function LessonBlocks({
  blocks,
  headingOffset = 0,
  assetUrl,
  equationAction,
  dataSaver = false,
  blockIds = false,
  typeset,
  premium = false,
}: {
  blocks: Block[];
  headingOffset?: number;
  assetUrl?: AssetUrl;
  /** SETTINGS-01: lesson diagrams load only when tapped (never used for questions, where a diagram may be needed). */
  dataSaver?: boolean;
  /** STUDY-TOOLS-01: e.g. "Save formula" under each top-level equation (its index in the lesson body). */
  equationAction?: (index: number) => ReactNode;
  /** Give each block an id (b0, b1, …) so language variants with one structure can return to the same place. */
  blockIds?: boolean;
  /** P01.S4.T2: equations already typeset on the server (`lib/typeset.ts`), by block index. */
  typeset?: Record<number, string | null>;
  /** BOOK-STYLE-01: the premium style of a chosen book (lib/book-style.ts `premiumBook`). */
  premium?: boolean;
}) {
  const view = (b: Block, i: number) => (
    <BlockView block={b} headingOffset={headingOffset} assetUrl={assetUrl} dataSaver={dataSaver} typeset={typeset?.[i]} premium={premium} />
  );
  // Each block keeps its own id (b0, b1, …), also inside a Quick Check card, so the language switch finds its place.
  // `data-kind` lets consecutive equations join into one card (globals.css `.lesson-flow`), as the book prints a run of
  // equations together.
  const wrap = (i: number, node: ReactNode) =>
    blockIds ? (
      <div id={`b${i}`} data-block="" data-kind={blocks[i]?.type} className="scroll-mt-20">
        {node}
      </div>
    ) : (
      <div data-kind={blocks[i]?.type}>{node}</div>
    );
  return (
    <div className="lesson-flow space-y-5 leading-relaxed" data-style={premium ? "premium" : undefined}>
      {blocks.map((b, i) => {
        if (isQuickCheck(blocks[i - 1], b)) return null; // drawn inside the card above
        if (isQuickCheck(b, blocks[i + 1])) {
          const level = Math.min(6, (b.level === 3 ? 3 : 2) + headingOffset);
          const Tag = `h${level}` as "h2" | "h3" | "h4" | "h5" | "h6";
          return (
            <section key={i} className="overflow-hidden rounded-xl border border-ok/40 bg-surface shadow-sm" aria-label={str(b.text)}>
              {wrap(
                i,
                <Tag dir="auto" className="bg-ok-soft px-4 py-2 text-base font-semibold text-ok">
                  {str(b.text)}
                </Tag>,
              )}
              <div className="px-4 py-3">{wrap(i + 1, view(blocks[i + 1], i + 1))}</div>
            </section>
          );
        }
        return (
          <Fragment key={i}>
            {wrap(i, view(b, i))}
            {b.type === "equation" && equationAction?.(i)}
          </Fragment>
        );
      })}
    </div>
  );
}

/** An archived image. Plain <img>: the copy is a re-encoded PNG from our own origin, sized by the browser. */
function ArchivedImage({ id, alt, assetUrl, dataSaver }: { id: string; alt: string; assetUrl?: AssetUrl; dataSaver?: boolean }) {
  if (!assetUrl || !id) return <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted">{alt}</p>;
  if (dataSaver) return <SaverImage src={assetUrl(id)} alt={alt} />;
  // eslint-disable-next-line @next/next/no-img-element -- an authenticated, immutable archive copy; no optimiser
  return <img src={assetUrl(id)} alt={alt} loading="lazy" className="mx-auto h-auto max-w-full rounded-lg border border-border bg-white" />;
}

/** §5.4 rule 5: the reviewed fallback for a block this renderer can't show natively. */
function FallbackView({ fb, assetUrl, dataSaver }: { fb: Fallback; assetUrl?: AssetUrl; dataSaver?: boolean }) {
  return (
    <figure className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3">
      {str(fb.image_asset_id) && <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(fb.text)} assetUrl={assetUrl} dataSaver={dataSaver} />}
      {str(fb.text) && <figcaption>{str(fb.text)}</figcaption>}
    </figure>
  );
}

function BlockView({
  block: b,
  headingOffset,
  assetUrl,
  dataSaver,
  typeset,
  premium = false,
}: {
  block: Block;
  headingOffset: number;
  assetUrl?: AssetUrl;
  dataSaver?: boolean;
  typeset?: string | null;
  premium?: boolean;
}) {
  const marks = bookErrors(b.book_errors);
  switch (b.type) {
    case "heading": {
      const level = Math.min(6, (b.level === 3 ? 3 : 2) + headingOffset);
      const Tag = `h${level}` as "h2" | "h3" | "h4" | "h5" | "h6";
      // Headings inside a topic ("Carbon monoxide (CO)" in 14.4.1) take their own colour, apart from the chapter's main
      // heading (14.4, accent) and the topic's title (14.4.1, text colour), so the three levels read apart (owner,
      // 2026-10-27).
      return (
        <Tag dir="auto" className={b.level === 3 ? "pt-1 text-lg font-semibold text-subheading" : "pt-2 text-xl font-semibold tracking-tight text-subheading"}>
          <Marked text={str(b.text)} marks={marks} />
        </Tag>
      );
    }
    case "paragraph":
      // BOOK-STYLE-01: a printed "Example:" (Roman Urdu "Misal:") becomes a label, and a lead-in line a small heading with an accent bar.
      if (premium && /^(example|misal)\s*:$/i.test(str(b.text).trim()) && !marks.length)
        return (
          <p className="inline-flex rounded-full bg-accent-soft px-3 py-0.5 text-xs font-semibold tracking-wide text-accent-strong uppercase">
            {str(b.text).trim().replace(/\s*:$/, "")}
          </p>
        );
      if (premium && leadIn(str(b.text)))
        return (
          <p dir="auto" className="flex items-baseline gap-2 font-semibold">
            <span aria-hidden className="h-[0.9em] w-1 shrink-0 translate-y-[0.1em] self-start rounded-full bg-accent" />
            <span>
              <Marked text={str(b.text)} marks={marks} />
            </span>
          </p>
        );
      return (
        <p dir="auto" className="whitespace-pre-line">
          <Marked text={str(b.text)} marks={marks} />
        </p>
      );
    case "list": {
      const items = strs(b.items).map((t, i) => {
        // BOOK-STYLE-01: "Term: what it means" shows the term bold in the subject colour.
        const lead = premium ? leadTerm(t, marks) : null;
        return (
          <li key={i} dir="auto">
            {lead ? (
              <>
                <span className="font-semibold text-accent">
                  <Marked text={`${lead[0]}:`} marks={marks} />
                </span>{" "}
                <Marked text={lead[1]} marks={marks} />
              </>
            ) : (
              <Marked text={t} marks={marks} />
            )}
          </li>
        );
      });
      return b.ordered ? (
        <ol className="list-decimal space-y-2 pl-7 marker:font-semibold marker:text-accent">{items}</ol>
      ) : (
        <ul className="list-disc space-y-2 pl-7 marker:text-accent">{items}</ul>
      );
    }
    case "callout": {
      const tone = str(b.tone) || "note";
      const label = CALLOUT_LABEL[tone] ?? "Note";
      // A title that only repeats the label ("Book correction") is shown once.
      const title = str(b.title).trim().toLowerCase() === label.toLowerCase() ? "" : str(b.title);
      const box = tone === "note" && title ? bookBox(title) : null;
      const printed = tone === "note" && title; // a printed box: its title is the header
      return (
        <aside className={`rounded-xl border-l-4 px-5 py-4 shadow-sm ${box ? BOOK_BOX_STYLE[box] : (CALLOUT_STYLE[tone] ?? CALLOUT_STYLE.note)}`}>
          {!printed && <p className="text-xs font-semibold tracking-wide text-muted uppercase">{label}</p>}
          {title && (
            <p dir="auto" className={printed ? `mb-1 font-semibold ${box ? BOOK_BOX_HEAD[box] : ""}` : "font-semibold"}>
              <Marked text={title} marks={marks} />
            </p>
          )}
          <p dir="auto" className="whitespace-pre-line">
            <Marked text={str(b.text)} marks={marks} />
          </p>
        </aside>
      );
    }
    case "table": {
      // A comparison table: a real table on wide screens; below 40rem each row folds into a card (globals.css
      // `.lesson-table`), with the first column naming the card and every other cell labelled by its column.
      const header = strs(b.header);
      const rows = Array.isArray(b.rows) ? (b.rows as unknown[]).map(strs) : [];
      // TABLE-MERGE-01: a merged cell spans its rows on wide screens; a hidden copy repeats it in each folded card.
      const merged = mergedColumns(b.merged_columns);
      const starts = mergeStarts(b.merge_starts);
      const spans = rowSpans(rows, merged, starts);
      const filled = fillMerged(rows, merged, starts);
      return (
        <table className="lesson-table w-full border-collapse text-sm">
          <caption className="mb-2 text-left font-medium">
            <Marked text={str(b.caption)} marks={marks} />
          </caption>
          <thead>
            <tr>
              {header.map((h, i) => (
                <th key={i} scope="col" className="border border-border bg-surface-muted px-3 py-2 text-left">
                  <Marked text={h} marks={marks} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) =>
                  spans[i][j] === 0 ? (
                    <td key={j} data-label={header[j] ?? ""} className="merged-repeat border border-border px-3 py-2 align-top">
                      <Marked text={filled[i][j]} marks={marks} />
                    </td>
                  ) : (
                    <td
                      key={j}
                      rowSpan={spans[i][j] > 1 ? spans[i][j] : undefined}
                      data-label={header[j] ?? ""}
                      className={`border border-border px-3 py-2 ${spans[i][j] > 1 ? "align-middle font-medium" : "align-top"}`}>
                      <Marked text={c} marks={marks} />
                    </td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      );
    }
    case "checkpoint": {
      // ANSWER-FIGURE-01: a drawn answer sits inside the check and appears only with the revealed answer.
      const af = (b.answer_figure ?? null) as { asset_version_id?: unknown; alt?: unknown; caption?: unknown; long_description?: unknown } | null;
      const answerFigure =
        af && str(af.asset_version_id) ? (
          <figure className="space-y-2 rounded-lg border border-border bg-surface p-3">
            <ArchivedImage id={str(af.asset_version_id)} alt={str(af.alt)} assetUrl={assetUrl} dataSaver={dataSaver} />
            {str(af.caption) && <figcaption className="text-sm text-muted">{str(af.caption)}</figcaption>}
            {str(af.long_description) && (
              <details className="text-sm">
                <summary className="cursor-pointer">Describe this diagram</summary>
                <p className="mt-1 whitespace-pre-line">{str(af.long_description)}</p>
              </details>
            )}
          </figure>
        ) : undefined;
      return (
        <Checkpoint
          mode={b.mode === "self_check" ? "self_check" : "question"}
          prompt={str(b.prompt)}
          options={Array.isArray(b.options) ? (b.options as { id: string; text: string }[]) : []}
          answerId={typeof b.answer_id === "string" ? b.answer_id : null}
          explanation={str(b.explanation)}
          answerFigure={answerFigure}
        />
      );
    }
    case "equation": {
      // Typeset on the web (P01.S4.T2), always with the text equivalent. The reviewed static rendering (§5.4: required
      // before publication while the apps have no equation renderer) shows when typesetting is off or fails. A printed
      // error is shown once, in red inside the formula (BOOK-CORRECTION-01); the text equivalent marks it too.
      const fb = (b.fallback ?? {}) as Fallback;
      return (
        <Equation
          latex={markLatex(str(b.latex), marks)}
          display={b.display !== false}
          textAlt={str(b.text_alt)}
          textView={marks.length ? <Marked text={str(b.text_alt)} marks={marks} /> : undefined}
          dataSaver={dataSaver}
          typeset={typeset}
          fallback={
            str(fb.image_asset_id) ? (
              <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(b.text_alt)} assetUrl={assetUrl} dataSaver={dataSaver} />
            ) : null
          }
        />
      );
    }
    case "example":
      return (
        <section
          className={`space-y-2 rounded-lg border border-border bg-surface px-4 py-3 ${premium ? "border-l-4 border-l-accent shadow-sm" : ""}`}
          aria-label={`Worked example: ${str(b.title)}`}>
          <p className={`text-xs font-semibold tracking-wide uppercase ${premium ? "text-accent" : "text-muted"}`}>Worked example</p>
          <p className="font-semibold">
            <Marked text={str(b.title)} marks={marks} />
          </p>
          <p className="whitespace-pre-line">
            <Marked text={str(b.problem)} marks={marks} />
          </p>
          <ol className="list-decimal space-y-1 pl-6">
            {strs(b.steps).map((step, i) => (
              <li key={i} className="whitespace-pre-line">
                <Marked text={step} marks={marks} />
              </li>
            ))}
          </ol>
          {str(b.answer) && (
            <p className="whitespace-pre-line">
              <span className="font-semibold">Answer: </span>
              <Marked text={str(b.answer)} marks={marks} />
            </p>
          )}
        </section>
      );
    case "code":
      // CODE-BLOCK-01: a program as printed; spaces and line breaks are kept, long lines scroll sideways.
      return (
        <figure className="space-y-2">
          {str(b.caption) && (
            <figcaption className="text-sm font-medium text-muted">
              <Marked text={str(b.caption)} marks={marks} />
            </figcaption>
          )}
          <pre
            className="overflow-x-auto rounded-xl border border-border bg-surface-muted px-4 py-3 font-mono text-[0.9rem] leading-6"
            tabIndex={0}
            aria-label={`${str(b.language) || "Program"} code${str(b.caption) ? `: ${str(b.caption)}` : ""}`}>
            <code>
              <Marked text={str(b.text)} marks={marks} />
            </code>
          </pre>
        </figure>
      );
    case "diagram":
      return (
        <figure className="space-y-2">
          <ArchivedImage id={str(b.asset_version_id)} alt={str(b.alt)} assetUrl={assetUrl} dataSaver={dataSaver} />
          <figcaption className="text-sm text-muted">{str(b.caption)}</figcaption>
          {str(b.long_description) && (
            <details className="text-sm">
              <summary className="cursor-pointer">Describe this diagram</summary>
              <p className="mt-1 whitespace-pre-line">{str(b.long_description)}</p>
            </details>
          )}
        </figure>
      );
    case "model3d": {
      const poster = str(b.poster_asset_version_id);
      const frames = strs(b.frames).filter(Boolean);
      if (!assetUrl || !poster) {
        return <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted">{str(b.alt)}</p>;
      }
      return (
        <Model3DFigure
          poster={assetUrl(poster)}
          frames={frames.map(assetUrl)}
          alt={str(b.alt)}
          caption={str(b.caption)}
          labels={strs(b.labels).filter(Boolean)}
          longDescription={str(b.long_description)}
          dataSaver={!!dataSaver}
        />
      );
    }
    case "scene":
      return (
        <figure className="space-y-2">
          <BacterialShapes />
          <figcaption className="text-sm text-muted">{str(b.caption)}</figcaption>
          <p className="text-sm">{str(b.alt)}</p>
          {str(b.long_description) && <p className="text-sm whitespace-pre-line text-muted">{str(b.long_description)}</p>}
        </figure>
      );
    case "handout":
      return (
        <p className="rounded-lg border border-border bg-surface px-4 py-3">
          {assetUrl ? (
            <a href={assetUrl(str(b.asset_version_id))} download className="font-medium text-accent underline underline-offset-2">
              Download: {str(b.title)} (PDF)
            </a>
          ) : (
            <span className="font-medium">Handout: {str(b.title)}</span>
          )}
          {str(b.description) && <span className="block text-sm text-muted">{str(b.description)}</span>}
        </p>
      );
    default: {
      const fb = (b.fallback ?? null) as Fallback | null;
      if (fb && (str(fb.text) || str(fb.image_asset_id))) return <FallbackView fb={fb} assetUrl={assetUrl} dataSaver={dataSaver} />;
      return (
        <p role="note" className="rounded-lg border border-warn bg-warn-soft px-4 py-3 text-sm">
          This part of the lesson needs a newer version of the app to display.
        </p>
      );
    }
  }
}

/** Original shapes for topic 1.1. A still diagram in the lesson remains readable if this view is unused. */
function BacterialShapes() {
  const shapes = [
    { name: "Coccus", detail: "spherical", path: "M36 8a16 16 0 1 0 0.1 0z" },
    { name: "Bacillus", detail: "rod-shaped", path: "M8 20h40a12 12 0 0 1 0 24H8a12 12 0 0 1 0-24z" },
    { name: "Vibrio", detail: "comma-shaped", path: "M48 16c-20 0-28 10-28 24 0 8 6 14 16 14" },
    { name: "Spirillum", detail: "spiral-shaped", path: "M8 40c8-16 16-16 24 0s16 16 24 0" },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-4" aria-label="Four bacterial forms">
      {shapes.map((shape) => (
        <div key={shape.name} className="flex flex-col items-center gap-1 text-center">
          <svg viewBox="0 0 64 64" className="h-16 w-16 text-accent" role="img" aria-label={`${shape.name}, ${shape.detail}`}>
            <path d={shape.path} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          </svg>
          <p className="text-sm font-medium">{shape.name}</p>
          <p className="text-xs text-muted">{shape.detail}</p>
        </div>
      ))}
    </div>
  );
}
