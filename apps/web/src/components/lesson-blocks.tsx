import { Fragment, type ReactNode } from "react";
import { Checkpoint } from "@/components/checkpoint";
import { Equation } from "@/components/equation";
import { Model3DFigure } from "@/components/model3d-figure";
import { SaverImage } from "@/components/saver-image";
import { bookErrors, markPieces } from "@/lib/book-errors";

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

/** Text with the textbook's wrong passages marked in red (BOOK-CORRECTION-01). */
function Marked({ text, marks }: { text: string; marks: string[] }) {
  return (
    <>
      {markPieces(text, marks).map((p, i) =>
        p.error ? (
          <mark key={i} title="Printed in the book; see the book correction" className="rounded-sm bg-danger-soft px-0.5 text-danger">
            {p.text}
          </mark>
        ) : (
          <Fragment key={i}>{p.text}</Fragment>
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
}) {
  return (
    <div className="space-y-5 leading-relaxed">
      {blocks.map((b, i) => (
        <Fragment key={i}>
          {blockIds ? (
            <div id={`b${i}`} data-block="" className="scroll-mt-20">
              <BlockView block={b} headingOffset={headingOffset} assetUrl={assetUrl} dataSaver={dataSaver} typeset={typeset?.[i]} />
            </div>
          ) : (
            <BlockView block={b} headingOffset={headingOffset} assetUrl={assetUrl} dataSaver={dataSaver} typeset={typeset?.[i]} />
          )}
          {b.type === "equation" && equationAction?.(i)}
        </Fragment>
      ))}
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
}: {
  block: Block;
  headingOffset: number;
  assetUrl?: AssetUrl;
  dataSaver?: boolean;
  typeset?: string | null;
}) {
  const marks = bookErrors(b.book_errors);
  switch (b.type) {
    case "heading": {
      const level = Math.min(6, (b.level === 3 ? 3 : 2) + headingOffset);
      const Tag = `h${level}` as "h2" | "h3" | "h4" | "h5" | "h6";
      return (
        <Tag dir="auto" className={b.level === 3 ? "text-lg font-semibold" : "text-xl font-semibold tracking-tight"}>
          <Marked text={str(b.text)} marks={marks} />
        </Tag>
      );
    }
    case "paragraph":
      return (
        <p dir="auto" className="whitespace-pre-line">
          <Marked text={str(b.text)} marks={marks} />
        </p>
      );
    case "list": {
      const items = strs(b.items).map((t, i) => (
        <li key={i} dir="auto">
          <Marked text={t} marks={marks} />
        </li>
      ));
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
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">{CALLOUT_LABEL[tone] ?? "Note"}</p>
          {str(b.title) && (
            <p dir="auto" className="font-semibold">
              {str(b.title)}
            </p>
          )}
          <p dir="auto" className="whitespace-pre-line">
            {str(b.text)}
          </p>
        </aside>
      );
    }
    case "table": {
      // A comparison table: a real table on wide screens; below 40rem each row folds into a card (globals.css
      // `.lesson-table`), with the first column naming the card and every other cell labelled by its column.
      const header = strs(b.header);
      const rows = Array.isArray(b.rows) ? (b.rows as unknown[]).map(strs) : [];
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
                {r.map((c, j) => (
                  <td key={j} data-label={header[j] ?? ""} className="border border-border px-3 py-2 align-top">
                    <Marked text={c} marks={marks} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
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
    case "equation": {
      // Typeset on the web (P01.S4.T2), always with the text equivalent. The reviewed static rendering (§5.4: required
      // before publication while the apps have no equation renderer) shows when typesetting is off or fails.
      const fb = (b.fallback ?? {}) as Fallback;
      const equation = (
        <Equation
          latex={str(b.latex)}
          display={b.display !== false}
          textAlt={str(b.text_alt)}
          dataSaver={dataSaver}
          typeset={typeset}
          fallback={
            str(fb.image_asset_id) ? (
              <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(b.text_alt)} assetUrl={assetUrl} dataSaver={dataSaver} />
            ) : null
          }
        />
      );
      // A printed equation with an error: outlined in red, its wrong part marked in the text equivalent.
      if (!marks.length) return equation;
      return (
        <div className="space-y-1 rounded-lg border-2 border-danger px-3 py-2">
          {equation}
          <p dir="auto" className="text-sm">
            <Marked text={str(b.text_alt)} marks={marks} />
          </p>
        </div>
      );
    }
    case "example":
      return (
        <section className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3" aria-label={`Worked example: ${str(b.title)}`}>
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">Worked example</p>
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
