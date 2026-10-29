// Native renderer for content blocks (schema v1, roadmap §5.4). Renderer version 2 on Android/iOS: text blocks render
// natively, comparison tables become cards, and `model3d` blocks show a poster render with a drag-to-rotate turntable.
// An unknown or unsupported block shows its reviewed fallback, or an explicit "update required" note instead of failing.
import { Image } from "expo-image";
import { createContext, Fragment, useContext, useState, type ReactNode } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Checkpoint } from "@/components/checkpoint";
import { CodeRunner } from "@/components/code-runner";
import { FigureViewer } from "@/components/figure-viewer";
import { Model3D } from "@/components/model3d";
import { LinkButton, T } from "@/components/ui";
import { CodeColors, Fonts, Radius, Space } from "@/constants/theme";
import { useScheme, useTheme } from "@/hooks/use-theme";
import { bookErrors, markPieces } from "@/lib/book-errors";
import { codeRuns } from "@/lib/code-highlight";
import { leadIn, leadTerm } from "@/lib/book-style";
import { comparisonCards } from "@/lib/lesson-tables";
import { fillMerged, mergedColumns, mergeStarts } from "@/lib/table-merge";

export const NATIVE_RENDERER_VERSION = 2;

type Block = { type: string; [key: string]: unknown };
const str = (v: unknown) => (typeof v === "string" ? v : "");
const strs = (v: unknown) => (Array.isArray(v) ? v.map(str) : []);

/** Where an archived asset version can be loaded on this screen (P07.S1.T1): a lesson's own files, with the session. */
export type AssetSource = (versionId: string) => { uri: string; headers?: Record<string, string> };
type Fallback = { text?: unknown; image_asset_id?: unknown; alt?: unknown };

const CALLOUT_LABEL: Record<string, string> = {
  definition: "Definition",
  note: "Note",
  tip: "Tip",
  warning: "Take care",
  correction: "Book correction",
};

/** A program with its parts coloured (CODE-HIGHLIGHT-01, theme.ts `CodeColors`) and the book's errors still in red. */
function Code({ text, language, marks }: { text: string; language: string; marks: string[] }) {
  const c = useTheme();
  const k = CodeColors[useScheme()];
  return (
    <>
      {codeRuns(text, language, markPieces(text, marks)).map((r, i) =>
        r.error ? (
          <Text key={i} style={{ color: c.danger, backgroundColor: c.dangerSoft, fontWeight: "600" }}>
            {r.text}
          </Text>
        ) : r.kind === "plain" ? (
          <Fragment key={i}>{r.text}</Fragment>
        ) : (
          <Text
            key={i}
            style={{ color: k[r.kind], fontStyle: r.kind === "comment" ? "italic" : "normal", fontWeight: r.kind === "keyword" ? "600" : "normal" }}>
            {r.text}
          </Text>
        ),
      )}
    </>
  );
}

/** Text with the textbook's wrong passages marked in red (BOOK-CORRECTION-01). Nested Text keeps it one paragraph. */
function Marked({ text, marks }: { text: string; marks: string[] }) {
  const c = useTheme();
  if (!marks.length) return <>{text}</>;
  return (
    <>
      {markPieces(text, marks).map((p, i) =>
        p.error ? (
          <Text key={i} style={{ color: c.danger, backgroundColor: c.dangerSoft, fontWeight: "600" }}>
            {p.text}
          </Text>
        ) : (
          <Fragment key={i}>{p.text}</Fragment>
        ),
      )}
    </>
  );
}

/** READER-STYLE-01: the book's printed boxes by their title (same rule as the web). */
function bookBox(title: string): "keep" | "know" | null {
  if (/^keep in mind/i.test(title)) return "keep";
  if (/^(do you know|did you know|for your information|interesting information|tidbits?|point to ponder|ponder upon)/i.test(title)) return "know";
  return null;
}

/** A printed "Quick Check" heading followed by its questions: one card, as the book prints it. */
function isQuickCheck(b: Block | undefined, next: Block | undefined) {
  return b?.type === "heading" && /^(quick check|self[- ]assessment)\b/i.test(str(b.text)) && next?.type === "list";
}

function QuickCheck({ title, children }: { title: string; children: ReactNode }) {
  const c = useTheme();
  return (
    <View style={{ borderWidth: 1, borderColor: c.ok, borderRadius: Radius.md, overflow: "hidden" }}>
      <View style={{ backgroundColor: c.okSoft, paddingHorizontal: Space.md, paddingVertical: Space.sm }}>
        <T accessibilityRole="header" style={{ fontWeight: "700", color: c.ok }}>
          {title}
        </T>
      </View>
      <View style={{ padding: Space.md }}>{children}</View>
    </View>
  );
}

/** BOOK-STYLE-01: the premium style of a chosen book (lib/book-style.ts `premiumBook`), read by every block. */
const Premium = createContext(false);
/** CODE-RUNNER-01: Python programs marked runnable get "Run karein" (the Roman Urdu lesson). */
const Runnable = createContext(false);
/** BOOK-EXERCISES-01: the words on each self-check's reveal button (the checkpoint's own label otherwise). */
const RevealLabel = createContext<string | undefined>(undefined);

export function LessonBlocks({
  blocks,
  assetSource,
  equationAction,
  dataSaver = false,
  onBlockLayout,
  premium = false,
  runnable = false,
  revealLabel,
}: {
  blocks: Block[];
  assetSource?: AssetSource;
  /** SETTINGS-01: lesson diagrams load only when tapped (never for questions, where a diagram may be needed). */
  dataSaver?: boolean;
  /** STUDY-TOOLS-01: e.g. "Save formula" under each top-level equation (its index in the lesson body). */
  equationAction?: (index: number) => ReactNode;
  /** Where each block sits (y within this list), so a language switch can return to the same place. */
  onBlockLayout?: (index: number, y: number) => void;
  premium?: boolean;
  runnable?: boolean;
  revealLabel?: string;
}) {
  return (
    <RevealLabel.Provider value={revealLabel}>
    <Runnable.Provider value={runnable}>
    <Premium.Provider value={premium}>
    <View style={{ gap: Space.lg }}>
      {blocks.map((b, i) => {
        if (isQuickCheck(blocks[i - 1], b)) return null; // drawn inside the card above
        if (isQuickCheck(b, blocks[i + 1])) {
          // Both blocks report the card's place, so a language switch still lands on it.
          return (
            <View
              key={i}
              onLayout={
                onBlockLayout
                  ? (e) => {
                      onBlockLayout(i, e.nativeEvent.layout.y);
                      onBlockLayout(i + 1, e.nativeEvent.layout.y);
                    }
                  : undefined
              }>
              <QuickCheck title={str(b.text)}>
                <BlockView block={blocks[i + 1]} assetSource={assetSource} dataSaver={dataSaver} />
              </QuickCheck>
            </View>
          );
        }
        // READER-STYLE-01: a run of equations printed together sits close, like one card.
        const joined = b.type === "equation" && blocks[i - 1]?.type === "equation" && !equationAction;
        return (
          <Fragment key={i}>
            <View
              style={joined ? { marginTop: Space.xs - Space.lg } : undefined}
              onLayout={onBlockLayout ? (e) => onBlockLayout(i, e.nativeEvent.layout.y) : undefined}>
              <BlockView block={b} assetSource={assetSource} dataSaver={dataSaver} />
            </View>
            {b.type === "equation" && equationAction?.(i)}
          </Fragment>
        );
      })}
    </View>
    </Premium.Provider>
    </Runnable.Provider>
    </RevealLabel.Provider>
  );
}

/** A figure plate: archived PNGs have white backgrounds, so the plate stays white in both themes. Tapping it opens the
 * figure full screen to pinch-zoom its labels (DIAGRAM-ZOOM-01). */
function ArchivedImage({
  id,
  alt,
  caption,
  assetSource,
  dataSaver,
}: {
  id: string;
  alt: string;
  caption?: string;
  assetSource?: AssetSource;
  dataSaver?: boolean;
}) {
  const c = useTheme();
  const [shown, setShown] = useState(false);
  const [open, setOpen] = useState(false);
  if (assetSource && id && dataSaver && !shown) {
    return (
      <View style={{ borderWidth: 1, borderStyle: "dashed", borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.sm }}>
        <T variant="small">{alt}</T>
        <LinkButton label="Show diagram (data saver is on)" onPress={() => setShown(true)} />
      </View>
    );
  }
  if (!assetSource || !id) {
    return (
      <View style={{ borderWidth: 1, borderStyle: "dashed", borderColor: c.border, borderRadius: Radius.sm, padding: Space.md }}>
        <T variant="small">{alt}</T>
      </View>
    );
  }
  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="imagebutton"
        accessibilityLabel={alt}
        accessibilityHint="Opens the diagram full screen so you can zoom in"
        style={{ backgroundColor: "#ffffff", borderWidth: 1, borderColor: c.border, borderRadius: Radius.md, overflow: "hidden" }}>
        <Image source={assetSource(id)} contentFit="contain" style={{ width: "100%", aspectRatio: 4 / 3 }} />
        <View
          pointerEvents="none"
          style={{ position: "absolute", right: Space.sm, bottom: Space.sm, backgroundColor: "rgba(17,19,23,0.72)", borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 3 }}>
          <T variant="small" style={{ color: "#ffffff", fontWeight: "600" }}>
            Tap to zoom
          </T>
        </View>
      </Pressable>
      {open ? <FigureViewer source={assetSource(id)} alt={alt} caption={caption} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function Lines({ items, ordered, marks = [] }: { items: string[]; ordered: boolean; marks?: string[] }) {
  const c = useTheme();
  const premium = useContext(Premium);
  return (
    <View style={{ gap: Space.sm }} accessibilityRole="list">
      {items.map((item, i) => (
        <View key={i} style={{ flexDirection: "row", gap: Space.sm }}>
          <T style={{ width: 24, textAlign: "right", color: c.accent, fontWeight: "700" }}>{ordered ? `${i + 1}.` : "•"}</T>
          <T style={{ flex: 1 }}>
            <Item text={item} marks={premium ? marks : null} />
          </T>
        </View>
      ))}
    </View>
  );
}

/** BOOK-STYLE-01: "Term: what it means" shows the term bold in the subject colour (premium books; `marks` null = plain). */
function Item({ text, marks }: { text: string; marks: string[] | null }) {
  const c = useTheme();
  const lead = marks ? leadTerm(text, marks) : null;
  if (!lead) return <Marked text={text} marks={marks ?? []} />;
  return (
    <>
      <Text style={{ fontWeight: "600", color: c.accent }}>
        <Marked text={`${lead[0]}:`} marks={marks ?? []} />
      </Text>{" "}
      <Marked text={lead[1]} marks={marks ?? []} />
    </>
  );
}

function BlockView({ block: b, assetSource, dataSaver }: { block: Block; assetSource?: AssetSource; dataSaver?: boolean }) {
  const c = useTheme();
  const premium = useContext(Premium);
  const runnable = useContext(Runnable);
  const revealLabel = useContext(RevealLabel);
  const marks = bookErrors(b.book_errors);
  switch (b.type) {
    case "heading":
      // Headings inside a topic take their own colour, apart from the chapter's main heading (accent) and the topic's
      // title (text colour), so the three levels read apart (owner, 2026-10-27). Inside the lesson the two levels read
      // apart too (owner, 2026-10-29): a section heading is blue and bold with a rule under it; its sub-heading is
      // smaller, in the heading colour, with a blue bar at its start.
      return b.level === 3 ? (
        <View style={{ marginTop: Space.xs, borderLeftWidth: 3, borderLeftColor: c.subheading, paddingLeft: Space.sm }}>
          <T variant="subheading" accessibilityRole="header" style={{ color: c.heading }}>
            <Marked text={str(b.text)} marks={marks} />
          </T>
        </View>
      ) : (
        <View style={{ marginTop: Space.sm, borderBottomWidth: 1, borderBottomColor: c.border, paddingBottom: Space.xs }}>
          <T variant="heading" accessibilityRole="header" style={{ color: c.subheading, fontWeight: "700" }}>
            <Marked text={str(b.text)} marks={marks} />
          </T>
        </View>
      );
    case "paragraph":
      // BOOK-STYLE-01: a printed "Example:" (Roman Urdu "Misal:") becomes a label, and a lead-in line a small heading with an accent bar.
      if (premium && /^(example|misal)\s*:$/i.test(str(b.text).trim()) && !marks.length)
        return (
          <View style={{ alignSelf: "flex-start", backgroundColor: c.accentSoft, borderRadius: 999, paddingHorizontal: Space.md, paddingVertical: 2 }}>
            <T variant="eyebrow" style={{ color: c.accent }}>
              {str(b.text).trim().replace(/\s*:$/, "")}
            </T>
          </View>
        );
      if (premium && leadIn(str(b.text)))
        return (
          <View style={{ borderLeftWidth: 4, borderLeftColor: c.accent, borderRadius: 2, paddingLeft: Space.sm }}>
            <T style={{ fontWeight: "600" }}>
              <Marked text={str(b.text)} marks={marks} />
            </T>
          </View>
        );
      return (
        <T>
          <Marked text={str(b.text)} marks={marks} />
        </T>
      );
    case "list":
      return <Lines items={strs(b.items)} ordered={b.ordered === true} marks={marks} />;
    case "callout": {
      const tone = str(b.tone) || "note";
      // A tip is green, as on the web: the diagram explanations ("Understanding the diagram") use it. So is a book
      // correction (BOOK-CORRECTION-01).
      const green = tone === "tip" || tone === "correction";
      const border = tone === "warning" ? c.warn : tone === "definition" ? c.accent : green ? c.ok : c.border;
      const bg = tone === "warning" ? c.warnSoft : tone === "definition" ? c.accentSoft : green ? c.okSoft : c.surfaceMuted;
      const label = CALLOUT_LABEL[tone] ?? "Note";
      // A title that only repeats the label ("Book correction") is shown once.
      const title = str(b.title).trim().toLowerCase() === label.toLowerCase() ? "" : str(b.title);
      // READER-STYLE-01: a titled note is one of the book's printed boxes; its title is the header, in the book's colour.
      const printed = tone === "note" && !!title;
      const box = printed ? bookBox(title) : null;
      const boxBorder = box === "keep" ? c.warn : box === "know" ? c.accent : border;
      const boxBg = box === "keep" ? c.warnSoft : box === "know" ? c.accentSoft : bg;
      return (
        <View style={{ borderLeftWidth: 4, borderLeftColor: boxBorder, backgroundColor: boxBg, borderRadius: Radius.md, padding: Space.md, gap: Space.xs }}>
          {printed ? null : (
            <T variant="eyebrow" style={{ color: tone === "warning" ? c.warn : tone === "definition" ? c.accent : green ? c.ok : c.muted }}>
              {label}
            </T>
          )}
          {title ? (
            <T style={{ fontWeight: "700", color: box === "keep" ? c.warn : box === "know" ? c.accent : undefined }}>
              <Marked text={title} marks={marks} />
            </T>
          ) : null}
          <T>
            <Marked text={str(b.text)} marks={marks} />
          </T>
        </View>
      );
    }
    case "table": {
      const header = strs(b.header);
      // TABLE-MERGE-01: a cell the book merges over several rows is repeated in each card, so every card is complete.
      const rows = fillMerged(
        Array.isArray(b.rows) ? (b.rows as unknown[]).map(strs) : [],
        mergedColumns(b.merged_columns),
        mergeStarts(b.merge_starts),
      );
      const cards = comparisonCards(header, rows);
      return (
        <View style={{ gap: Space.sm }} accessibilityLabel={`Table: ${str(b.caption)}`}>
          <T style={{ fontWeight: "600", color: premium ? c.accent : c.text }}>
            <Marked text={str(b.caption)} marks={marks} />
          </T>
          {cards ? (
            cards.map((card, i) => (
              <View key={i} style={{ borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, borderRadius: Radius.md, padding: Space.md, gap: Space.xs }}>
                <T style={{ fontWeight: "700", color: c.accent }}>
                  <Marked text={card.title} marks={marks} />
                </T>
                {card.fields.map((f) => (
                  <View key={f.label} style={{ flexDirection: "row", gap: Space.sm }}>
                    <T variant="small" style={{ width: 104, fontWeight: "600" }}>
                      {f.label}
                    </T>
                    <T style={{ flex: 1 }}>
                      <Marked text={f.value} marks={marks} />
                    </T>
                  </View>
                ))}
              </View>
            ))
          ) : header.length === 1 ? (
            // A one-column table is a boxed list in the book: its items sit in two columns (owner, 2026-10-29).
            <View style={{ borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, borderRadius: Radius.md, overflow: "hidden" }}>
              <T style={{ fontWeight: "700", padding: Space.sm, backgroundColor: c.surfaceMuted }}>
                <Marked text={header[0]} marks={marks} />
              </T>
              <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
                {rows.map((r, i) => (
                  <View key={i} style={{ width: "50%", padding: Space.sm, borderTopWidth: 1, borderColor: c.border }}>
                    <T variant="small">
                      <Marked text={r[0] ?? ""} marks={marks} />
                    </T>
                  </View>
                ))}
              </View>
            </View>
          ) : (
            <Lines items={rows.flat()} ordered={false} marks={marks} />
          )}
        </View>
      );
    }
    case "checkpoint": {
      // ANSWER-FIGURE-01: a drawn answer sits inside the check and appears only with the revealed answer.
      const af = (b.answer_figure ?? null) as { asset_version_id?: unknown; alt?: unknown; caption?: unknown; long_description?: unknown } | null;
      const answerFigure =
        af && str(af.asset_version_id) ? (
          <View style={{ gap: Space.xs }}>
            <ArchivedImage id={str(af.asset_version_id)} alt={str(af.alt)} caption={str(af.caption)} assetSource={assetSource} dataSaver={dataSaver} />
            {str(af.caption) ? <T variant="small">{str(af.caption)}</T> : null}
            {str(af.long_description) ? <Description text={str(af.long_description)} /> : null}
          </View>
        ) : undefined;
      // CHECKPOINT-TABLE-01: a comparison answer side by side, also shown only with the revealed answer.
      const at = (b.answer_table ?? null) as { header?: unknown; rows?: unknown } | null;
      const head = strs(at?.header);
      const answerTable =
        head.length && Array.isArray(at?.rows) ? (
          <View style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, overflow: "hidden", backgroundColor: c.surface }}>
            {[head, ...(at.rows as unknown[]).map(strs)].map((r, i) => (
              <View key={i} style={{ flexDirection: "row", borderTopWidth: i ? 1 : 0, borderTopColor: c.border, backgroundColor: i ? c.surface : c.surfaceMuted }}>
                {r.map((cell, j) => (
                  <View key={j} style={{ flex: 1, padding: Space.sm, borderLeftWidth: j ? 1 : 0, borderLeftColor: c.border }}>
                    <T variant="small" style={{ fontWeight: i ? "400" : "700", color: c.text }}>
                      {cell}
                    </T>
                  </View>
                ))}
              </View>
            ))}
          </View>
        ) : null;
      return (
        <Checkpoint
          mode={b.mode === "self_check" ? "self_check" : "question"}
          prompt={str(b.prompt)}
          options={Array.isArray(b.options) ? (b.options as { id: string; text: string }[]) : []}
          answerId={typeof b.answer_id === "string" ? b.answer_id : null}
          explanation={str(b.explanation)}
          answerFigure={
            answerTable || answerFigure ? (
              <View style={{ gap: Space.sm }}>
                {answerTable}
                {answerFigure}
              </View>
            ) : undefined
          }
          revealLabel={revealLabel}
        />
      );
    }
    case "equation": {
      // Native renderer 2 has no typeset equations: show the reviewed static rendering and the text equivalent (§5.4).
      const fb = (b.fallback ?? {}) as Fallback;
      return (
        // A printed equation with an error shows its wrong part in red (BOOK-CORRECTION-01).
        <View style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.sm }}>
          {str(fb.image_asset_id) ? <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(b.text_alt)} assetSource={assetSource} dataSaver={dataSaver} /> : null}
          <T>
            <Marked text={str(b.text_alt)} marks={marks} />
          </T>
        </View>
      );
    }
    case "example":
      return (
        <View
          accessibilityLabel={`Worked example: ${str(b.title)}`}
          style={{
            borderWidth: 1,
            borderColor: c.border,
            borderRadius: Radius.sm,
            padding: Space.md,
            gap: Space.xs,
            ...(premium ? { borderLeftWidth: 4, borderLeftColor: c.accent } : null),
          }}>
          <T variant="eyebrow" style={{ color: premium ? c.accent : c.muted }}>
            Worked example
          </T>
          <T style={{ fontWeight: "600" }}>
            <Marked text={str(b.title)} marks={marks} />
          </T>
          <T>
            <Marked text={str(b.problem)} marks={marks} />
          </T>
          <Lines items={strs(b.steps)} ordered marks={marks} />
          {str(b.answer) ? (
            <T style={{ fontWeight: "600" }}>
              {"Answer: "}
              <Marked text={str(b.answer)} marks={marks} />
            </T>
          ) : null}
        </View>
      );
    case "code":
      // CODE-BLOCK-01: a program as printed; spaces and line breaks are kept, long lines scroll sideways.
      return (
        <View style={{ gap: Space.xs }} accessibilityLabel={`${str(b.language) || "Program"} code${str(b.caption) ? `: ${str(b.caption)}` : ""}`}>
          {str(b.caption) ? (
            <T variant="small" style={{ fontWeight: "600", color: c.muted }}>
              <Marked text={str(b.caption)} marks={marks} />
            </T>
          ) : null}
          <ScrollView horizontal style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.md, backgroundColor: c.surfaceMuted }} contentContainerStyle={{ padding: Space.md }}>
            <Text selectable style={{ fontFamily: Fonts?.mono, fontSize: 14, lineHeight: 21, color: c.text }}>
              <Code text={str(b.text)} language={str(b.language)} marks={marks} />
            </Text>
          </ScrollView>
          {runnable && b.runnable === true ? <CodeRunner code={str(b.text)} /> : null}
        </View>
      );
    case "diagram":
      return (
        <View style={{ gap: Space.xs }}>
          <ArchivedImage id={str(b.asset_version_id)} alt={str(b.alt)} caption={str(b.caption)} assetSource={assetSource} dataSaver={dataSaver} />
          <T variant="small">{str(b.caption)}</T>
          {str(b.long_description) ? <Description text={str(b.long_description)} /> : null}
        </View>
      );
    case "model3d":
      return (
        <Model3D
          poster={str(b.poster_asset_version_id)}
          frames={strs(b.frames).filter(Boolean)}
          alt={str(b.alt)}
          caption={str(b.caption)}
          labels={strs(b.labels).filter(Boolean)}
          longDescription={str(b.long_description)}
          assetSource={assetSource}
          dataSaver={dataSaver}
        />
      );
    case "scene":
      return (
        <View style={{ gap: Space.xs }}>
          <BacterialShapes />
          <T variant="small">{str(b.caption)}</T>
          <T>{str(b.alt)}</T>
          {str(b.long_description) ? <Description text={str(b.long_description)} /> : null}
        </View>
      );
    case "handout":
      // Saving a PDF on the device needs a share sheet this app doesn't include yet; handouts download on the website.
      return (
        <View style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.xs }}>
          <T style={{ fontWeight: "600" }}>{`Handout: ${str(b.title)}`}</T>
          {str(b.description) ? <T variant="small">{str(b.description)}</T> : null}
          <T variant="small">Download it from this lesson on the website.</T>
        </View>
      );
    default: {
      const fb = (b.fallback ?? null) as Fallback | null; // §5.4 rule 5: the reviewed fallback, when there is one
      if (fb && (str(fb.text) || str(fb.image_asset_id))) {
        return (
          <View style={{ gap: Space.xs }}>
            {str(fb.image_asset_id) ? <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(fb.text)} assetSource={assetSource} dataSaver={dataSaver} /> : null}
            {str(fb.text) ? <T>{str(fb.text)}</T> : null}
          </View>
        );
      }
      return (
        <View accessibilityRole="alert" style={{ backgroundColor: c.warnSoft, borderRadius: Radius.sm, padding: Space.md }}>
          <T variant="small">This part of the lesson needs a newer version of the app to display.</T>
        </View>
      );
    }
  }
}

/** A figure's long description, folded by default so the lesson stays readable; screen readers get the alt text anyway. */
function Description({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={{ gap: Space.xs }}>
      <LinkButton label={open ? "Hide the description" : "Describe this figure"} onPress={() => setOpen((o) => !o)} />
      {open ? <T variant="muted">{text}</T> : null}
    </View>
  );
}

function BacterialShapes() {
  const c = useTheme();
  const shapes = [
    { name: "Coccus", detail: "spherical", style: { width: 36, height: 36, borderRadius: 18 } },
    { name: "Bacillus", detail: "rod-shaped", style: { width: 56, height: 22, borderRadius: 11 } },
    { name: "Vibrio", detail: "comma-shaped", style: { width: 28, height: 36, borderRadius: 14, borderBottomRightRadius: 4 } },
    { name: "Spirillum", detail: "spiral-shaped", style: { width: 18, height: 40, borderRadius: 9 } },
  ];
  return (
    <View accessibilityLabel="Four bacterial forms" style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.md }}>
      {shapes.map((shape) => (
        <View key={shape.name} accessible accessibilityLabel={`${shape.name}, ${shape.detail}`} style={{ width: 88, alignItems: "center", gap: Space.xs }}>
          <View style={{ height: 48, justifyContent: "center" }}>
            <View style={{ borderWidth: 2, borderColor: c.accent, ...shape.style }} />
          </View>
          <T style={{ fontWeight: "600", textAlign: "center" }}>{shape.name}</T>
          <T variant="small" style={{ textAlign: "center" }}>{shape.detail}</T>
        </View>
      ))}
    </View>
  );
}
