import { Fragment, type ReactNode } from "react";
import { Checkpoint } from "@/components/checkpoint";
import { SaverImage } from "@/components/saver-image";

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
}: {
  blocks: Block[];
  headingOffset?: number;
  assetUrl?: AssetUrl;
  /** SETTINGS-01: lesson diagrams load only when tapped (never used for questions, where a diagram may be needed). */
  dataSaver?: boolean;
  /** STUDY-TOOLS-01: e.g. "Save formula" under each top-level equation (its index in the lesson body). */
  equationAction?: (index: number) => ReactNode;
}) {
  return (
    <div className="space-y-4 leading-relaxed">
      {blocks.map((b, i) => (
        <Fragment key={i}>
          <BlockView block={b} headingOffset={headingOffset} assetUrl={assetUrl} dataSaver={dataSaver} />
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

function BlockView({ block: b, headingOffset, assetUrl, dataSaver }: { block: Block; headingOffset: number; assetUrl?: AssetUrl; dataSaver?: boolean }) {
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
    case "equation": {
      // No typeset renderer ships yet (§5.4: equations need a reviewed fallback before publication). Show the reviewed
      // static rendering when there is one, always with the text equivalent; the source LaTeX helps staff check.
      const fb = (b.fallback ?? {}) as Fallback;
      return (
        <figure className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3">
          {str(fb.image_asset_id) && <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(b.text_alt)} assetUrl={assetUrl} dataSaver={dataSaver} />}
          <p>{str(b.text_alt)}</p>
          <figcaption className="font-mono text-xs text-muted">{str(b.latex)}</figcaption>
        </figure>
      );
    }
    case "example":
      return (
        <section className="space-y-2 rounded-lg border border-border bg-surface px-4 py-3" aria-label={`Worked example: ${str(b.title)}`}>
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">Worked example</p>
          <p className="font-semibold">{str(b.title)}</p>
          <p className="whitespace-pre-line">{str(b.problem)}</p>
          <ol className="list-decimal space-y-1 pl-6">
            {strs(b.steps).map((step, i) => (
              <li key={i} className="whitespace-pre-line">
                {step}
              </li>
            ))}
          </ol>
          {str(b.answer) && (
            <p className="whitespace-pre-line">
              <span className="font-semibold">Answer: </span>
              {str(b.answer)}
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
