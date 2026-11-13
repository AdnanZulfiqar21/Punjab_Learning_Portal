// Native renderer for content blocks (schema v1, roadmap §5.4). Renderer version 2 on Android/iOS: text blocks render
// natively, comparison tables become cards, and `model3d` blocks show a poster render with a drag-to-rotate turntable.
// An unknown or unsupported block shows its reviewed fallback, or an explicit "update required" note instead of failing.
import { Image } from "expo-image";
import { router } from "expo-router";
import { createContext, Fragment, useContext, useMemo, useState, type ReactNode } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Checkpoint } from "@/components/checkpoint";
import { CodeRunner } from "@/components/code-runner";
import { FigureViewer } from "@/components/figure-viewer";
import { Model3D } from "@/components/model3d";
import { LinkButton, T } from "@/components/ui";
import { CodeColors, Fonts, Radius, Space } from "@/constants/theme";
import { useScheme, useTheme } from "@/hooks/use-theme";
import { bookBoxKind, boxRow, isMarginNote, isSideBox, isSideFigure, type BookBoxKind } from "@/lib/book-box";
import { bookErrors, markPieces, styledPieces } from "@/lib/book-errors";
import { isListMarker, labelWidth, listLabel, splitLabel, type ListMarker } from "@/lib/book-list";
import { codeRuns } from "@/lib/code-highlight";
import { leadIn, leadTerm } from "@/lib/book-style";
import { splitQuestionNumber } from "@/lib/question-number";
import { findBlock, findRange } from "@/lib/find-in-book";
import { comparisonCards } from "@/lib/lesson-tables";
import { plainBlocks } from "@/lib/inline-math";
import { SOLVED_LABELS_EN, stepText, type SolvedLabels } from "@/lib/solved-labels";
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
/** MCQ-BOOK-LINK-01: opens the Learn topic that prints a practice question's passage, with that passage marked. */
function bookPress(ref: unknown): (() => void) | undefined {
  const r = (ref ?? null) as { topic_id?: unknown; quote?: unknown } | null;
  if (!r || typeof r.topic_id !== "string" || typeof r.quote !== "string") return undefined;
  const id = r.topic_id;
  const find = r.quote;
  return () => router.push({ pathname: "/topic/[id]", params: { id, find } });
}

function Marked({ text, marks, bold = [] }: { text: string; marks: string[]; bold?: string[] }) {
  const c = useTheme();
  const scheme = useScheme();
  const find = useContext(Find);
  const hit = find ? findRange(text, find) : null;
  if (hit) {
    // MCQ-BOOK-LINK-01: the book's words a practice question comes from, marked like a highlighter pen.
    return (
      <>
        <Find.Provider value={null}>
          <Marked text={text.slice(0, hit[0])} marks={marks} bold={bold} />
        </Find.Provider>
        <Text style={{ backgroundColor: scheme === "dark" ? "#b38f00" : "#ffe36b", color: scheme === "dark" ? "#fffdf5" : "#1c1a17" }}>
          {text.slice(hit[0], hit[1])}
        </Text>
        <Find.Provider value={null}>
          <Marked text={text.slice(hit[1])} marks={marks} bold={bold} />
        </Find.Provider>
      </>
    );
  }
  if (!marks.length && !bold.length) return <>{text}</>;
  return (
    <>
      {styledPieces(text, marks, bold).map((p, i) =>
        p.error ? (
          <Text key={i} style={{ color: c.danger, backgroundColor: c.dangerSoft, fontWeight: p.bold ? "700" : "600" }}>
            {p.text}
          </Text>
        ) : p.bold ? (
          // BOOK-BOLD-01: a term the book prints in bold
          <Text key={i} style={{ fontWeight: "700" }}>
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
/** QUESTION-NUMBER-01: a Practice page: each question's printed number is drawn apart from its words. */
const Numbered = createContext(false);
const Solved = createContext<SolvedLabels>(SOLVED_LABELS_EN);
/** MCQ-BOOK-LINK-01: the book's words to mark, given only to the block that holds them. */
const Find = createContext<string | null>(null);

export function LessonBlocks({
  blocks: authored,
  assetSource,
  equationAction,
  dataSaver = false,
  onBlockLayout,
  premium = false,
  runnable = false,
  revealLabel,
  solvedLabels = SOLVED_LABELS_EN,
  find,
  numbered = false,
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
  /** SOLVED-QUESTION-01: the words of a solved book question in the lesson's language. */
  solvedLabels?: SolvedLabels;
  /** MCQ-BOOK-LINK-01: the book's words to mark like a highlighter ("See in book" from a practice MCQ). */
  find?: string;
  /** QUESTION-NUMBER-01: a Practice page: each question's printed number is drawn apart from its words. */
  numbered?: boolean;
}) {
  // INLINE-MATH-01: formulas written in the text (\( … \), \[ … \]) read as plain text here.
  const blocks = useMemo(() => plainBlocks(authored) as Block[], [authored]);
  // The block drawn with the words (a side item is drawn in its paragraph's row, a quick check's question in its card).
  const target = find ? findBlock(blocks, find) : -1;
  const sideStart = target < 0 ? -1 : sideRunStart(blocks, target);
  const holder = target < 0 ? -1 : sideStart >= 0 ? sideStart : isQuickCheck(blocks[target - 1], blocks[target]) ? target - 1 : target;
  return (
    <Solved.Provider value={solvedLabels}>
    <Numbered.Provider value={numbered}>
    <RevealLabel.Provider value={revealLabel}>
    <Runnable.Provider value={runnable}>
    <Premium.Provider value={premium}>
    <View style={{ gap: Space.lg }}>
      {blocks.map((b, i) => {
        const el = renderAt(b, i);
        return i === holder && el ? (
          <Find.Provider key={`find-${i}`} value={find ?? null}>
            {el}
          </Find.Provider>
        ) : (
          el
        );
      })}
    </View>
    </Premium.Provider>
    </Runnable.Provider>
    </RevealLabel.Provider>
    </Numbered.Provider>
    </Solved.Provider>
  );

  function renderAt(b: Block, i: number): ReactNode {
        if (isQuickCheck(blocks[i - 1], b)) return null; // drawn inside the card above
        // BOOK-LAYOUT-01 and BOOK-BOX-01 on the phone (owner, 2026-11-08: "book wala format follow karo phr wo chahy boxes
        // hain ya figures"): what the book prints at the side of a paragraph (a figure marked side, a short printed box
        // or margin note) sits at the right of that paragraph, as printed; the same rule as the web's sideOrder.
        if (sideRunStart(blocks, i) >= 0) return null; // drawn in the row of its paragraph
        const run = sideRun(blocks, i);
        if (run > 0) {
          const side = Array.from({ length: run }, (_, k) => i + 1 + k);
          return (
            <View
              key={i}
              onLayout={
                onBlockLayout
                  ? (e) => {
                      onBlockLayout(i, e.nativeEvent.layout.y);
                      side.forEach((k) => onBlockLayout(k, e.nativeEvent.layout.y));
                    }
                  : undefined
              }>
              <SideRow
                text={b}
                side={side.map((k) => (
                  <BlockView key={k} block={blocks[k]} assetSource={assetSource} dataSaver={dataSaver} compact />
                ))}
                render={(block) => <BlockView block={block} assetSource={assetSource} dataSaver={dataSaver} />}
              />
            </View>
          );
        }
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
  }
}

/** A figure plate: archived PNGs have white backgrounds, so the plate stays white in both themes. Tapping it opens the
 * figure full screen to pinch-zoom its labels (DIAGRAM-ZOOM-01). */
function ArchivedImage({
  id,
  alt,
  caption,
  assetSource,
  dataSaver,
  compact,
}: {
  id: string;
  alt: string;
  caption?: string;
  assetSource?: AssetSource;
  dataSaver?: boolean;
  /** Beside the text: a smaller zoom hint. */
  compact?: boolean;
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
          <T variant="small" style={{ color: "#ffffff", fontWeight: "600", fontSize: compact ? 11 : undefined, lineHeight: compact ? 14 : undefined }}>
            {compact ? "Zoom" : "Tap to zoom"}
          </T>
        </View>
      </Pressable>
      {open ? <FigureViewer source={assetSource(id)} alt={alt} caption={caption} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

// BOOK-BOX-01: the header colour of each kind of printed box; the same values as globals.css (.book-box).
const BOOK_BOX_HEAD: Record<BookBoxKind, string> = {
  rule: "#2f5fb3",
  know: "#1f7a52",
  info: "#0e6f78",
  interesting: "#9a5b06",
  tidbit: "#b0245a",
  ponder: "#6d3aa8",
  teaser: "#4338ca",
  quiz: "#9d1b9f",
  check: "#2e6b30",
  keep: "#a3480a",
  activity: "#b4380f",
  fact: "#0f5f8a",
  outcomes: "#84650a",
};
// An untitled margin note: a gold edge and a pale yellow body, as on the web.
const MARGIN_NOTE = "#c9a227";
/** BOOK-LIST-01: about one character of the reading font, for a label column sized in characters. */
const LABEL_CH = 8.5;
const labelColumn = (marker: ListMarker, start: number, count: number) => labelWidth(marker, start, count) * LABEL_CH;

function Lines({
  items,
  ordered,
  marks = [],
  bold = [],
  start = 1,
  continued = false,
  marker,
}: {
  items: string[];
  ordered: boolean;
  /** BOOK-LIST-01: the label style the book prints ("i-", "(a)"); absent means plain numbers. */
  marker?: ListMarker;
  marks?: string[];
  bold?: string[];
  start?: number;
  /** The first item goes on from the item above it (cut by a side figure or box): no number of its own. */
  continued?: boolean;
}) {
  const c = useTheme();
  const premium = useContext(Premium);
  const booked = ordered && marker ? marker : null;
  const width = booked ? labelColumn(booked, start, items.length) : 24;
  return (
    <View style={{ gap: Space.sm }} accessibilityRole="list">
      {items.map((item, i) => (
        <View key={i} style={{ flexDirection: "row", gap: Space.sm }}>
          {booked ? (
            <T style={{ width }}>{continued && i === 0 ? "" : listLabel(booked, start + i)}</T>
          ) : (
            <T style={{ width: 24, textAlign: "right", color: c.accent, fontWeight: "700" }}>{continued && i === 0 ? "" : ordered ? `${start + i}.` : "•"}</T>
          )}
          <T style={{ flex: 1 }}>
            <Item text={item} marks={premium ? marks : null} bold={bold} />
          </T>
        </View>
      ))}
    </View>
  );
}

/** BOOK-STYLE-01: "Term: what it means" shows the term bold in the subject colour (premium books; `marks` null = plain). */
function Item({ text, marks, bold }: { text: string; marks: string[] | null; bold: string[] }) {
  const c = useTheme();
  const lead = marks ? leadTerm(text, marks) : null;
  if (!lead) return <Marked text={text} marks={marks ?? []} bold={bold} />;
  return (
    <>
      <Text style={{ fontWeight: "600", color: c.accent }}>
        <Marked text={`${lead[0]}:`} marks={marks ?? []} />
      </Text>{" "}
      <Marked text={lead[1]} marks={marks ?? []} bold={bold} />
    </>
  );
}

type Line = { text: string; y: number; height: number };

/** A paragraph or list with what the book prints at its side (owner, 2026-11-08: "jb figure khatam ho gaya hy to baki ka
 * text nechy lago"; then "abhe bhe right pr space khali hy" for a list): the text runs beside the side items only as far
 * down as they reach, and the rest continues across the full width below them, as the web's float does. React Native
 * has no float, so the text is laid out once, unseen, in the narrow column; the lines that fit beside the side items
 * stay there and the rest moves below (a list item cut in two goes on below without its number). */
function SideRow({ text, side, render }: { text: Block; side: ReactNode; render: (block: Block) => ReactNode }) {
  const [sideHeight, setSideHeight] = useState(0);
  const isList = text.type === "list";
  const items = isList ? strs(text.items) : text.type === "paragraph" ? [str(text.text)] : [];
  const [lines, setLines] = useState<(Line[] | undefined)[]>([]);
  // Plain computation: the React Compiler memoizes it.
  const split = ((): { item: number; at: number } | null => {
    if (!items.length || !sideHeight || items.some((_, i) => !lines[i])) return null;
    const gap = isList ? Space.sm : 0;
    let top = 0;
    for (let i = 0; i < items.length; i++) {
      const ls = lines[i]!;
      const height = ls.reduce((h, l) => Math.max(h, l.y + l.height), 0);
      if (top + height <= sideHeight + 2) {
        top += height + gap;
        continue;
      }
      // Item i reaches below the side items: the lines of it that still fit stay beside them.
      let k = 0;
      while (k < ls.length && top + ls[k].y + ls[k].height <= sideHeight + 2) k++;
      if (i === 0 && k === 0) k = 1; // at least one line beside the side items
      const at = ls.slice(0, k).reduce((n, l) => n + l.text.length, 0);
      return { item: i, at: Math.min(at, items[i].length) };
    }
    return null; // everything fits beside the side items
  })();

  const start = typeof text.start === "number" ? text.start : 1;
  let beside: Block = text;
  let below: Block[] = [];
  if (split) {
    const { item, at } = split;
    const head = items[item].slice(0, at).trimEnd();
    const tail = items[item].slice(at).trimStart();
    if (!isList) {
      beside = { ...text, text: head };
      below = tail ? [{ ...text, text: tail }] : [];
    } else {
      beside = { ...text, items: [...items.slice(0, item), ...(head ? [head] : [])] };
      if (tail) below.push({ ...text, items: [tail], start: start + item, continued: true });
      if (item + 1 < items.length) below.push({ ...text, items: items.slice(item + 1), start: start + item + 1 });
      if (!head && item === 0) beside = { ...text, items: [] };
    }
  }
  const besideEmpty = isList && strs(beside.items).length === 0;
  return (
    <View style={{ gap: isList ? Space.sm : 0 }}>
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: Space.md }}>
        <View style={{ flex: 1 }}>
          {/* the unseen layout of the text in this column */}
          <View
            aria-hidden
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
            pointerEvents="none"
            style={{ position: "absolute", left: 0, right: 0, opacity: 0, gap: isList ? Space.sm : 0 }}>
            {items.map((item, i) => (
              <View key={i} style={{ flexDirection: "row", gap: isList ? Space.sm : 0 }}>
                {isList ? <View style={{ width: isList && text.ordered === true && isListMarker(text.marker) ? labelColumn(text.marker, start, items.length) : 24 }} /> : null}
                <T
                  style={{ flex: 1 }}
                  onTextLayout={(e) => {
                    const ls = e.nativeEvent.lines.map((l) => ({ text: l.text, y: l.y, height: l.height }));
                    setLines((old) => {
                      const next = [...old];
                      next[i] = ls;
                      return next;
                    });
                  }}>
                  {item}
                </T>
              </View>
            ))}
          </View>
          {besideEmpty ? null : render(beside)}
        </View>
        <View style={{ width: "46%", gap: Space.sm }} onLayout={(e) => setSideHeight(e.nativeEvent.layout.height)}>
          {side}
        </View>
      </View>
      {below.map((block, i) => (
        <Fragment key={i}>{render(block)}</Fragment>
      ))}
    </View>
  );
}

/** The smaller type of a box at the side of the text (the web's 0.8em). */
const SIDE_TEXT = { fontSize: 13, lineHeight: 19 } as const;

/** Text that side items sit beside: a paragraph or a list. */
function besideText(b: Block | undefined): boolean {
  return b?.type === "paragraph" || b?.type === "list";
}

/** Printed at the side of the text: a figure marked side, or a short printed box or margin note. */
function atSide(b: Block | undefined): boolean {
  return isSideFigure(b) || isSideBox(b);
}

/** At a paragraph or list followed by side items, how many follow (0 elsewhere). Boxes the web draws side by side in
 * one row (boxRow) are not moved, as on the web. */
function sideRun(blocks: readonly Block[], i: number): number {
  if (!besideText(blocks[i])) return 0;
  let n = 0;
  while (atSide(blocks[i + 1 + n])) n++;
  return n > 0 && boxRow(blocks, i + 1) === 0 ? n : 0;
}

/** For a side item drawn in its paragraph's row, that paragraph's index; -1 otherwise. */
function sideRunStart(blocks: readonly Block[], i: number): number {
  let j = i;
  while (j > 0 && atSide(blocks[j])) {
    j--;
    if (sideRun(blocks, j) >= i - j) return j;
    if (!atSide(blocks[j])) break;
  }
  return -1;
}

function BlockView({ block: b, assetSource, dataSaver, compact }: { block: Block; assetSource?: AssetSource; dataSaver?: boolean; compact?: boolean }) {
  const c = useTheme();
  const scheme = useScheme();
  const premium = useContext(Premium);
  const runnable = useContext(Runnable);
  const revealLabel = useContext(RevealLabel);
  const solvedLabels = useContext(Solved);
  const numbered = useContext(Numbered);
  const marks = bookErrors(b.book_errors);
  const bold = bookErrors(b.bold); // BOOK-BOLD-01: the terms the book prints in bold
  switch (b.type) {
    case "heading":
      // Headings inside a topic take their own colour, apart from the chapter's main heading (accent) and the topic's
      // title (text colour), so the three levels read apart (owner, 2026-10-27). Inside the lesson the levels read apart
      // too (owner, 2026-10-29): a section (2) is blue and bold with a rule under it, a heading inside it (3) blue and
      // smaller, a numbered sub-heading (4) in the heading colour with a blue bar at its start.
      return b.level === 4 ? (
        <View style={{ marginTop: Space.xs, borderLeftWidth: 3, borderLeftColor: c.subheading, paddingLeft: Space.sm }}>
          <T variant="body" accessibilityRole="header" style={{ color: c.heading, fontSize: 17, fontWeight: "600" }}>
            <Marked text={str(b.text)} marks={marks} bold={bold} />
          </T>
        </View>
      ) : b.level === 3 ? (
        <T variant="subheading" accessibilityRole="header" style={{ marginTop: Space.xs, color: c.subheading, fontSize: 18, lineHeight: 25, fontWeight: "700" }}>
          <Marked text={str(b.text)} marks={marks} bold={bold} />
        </T>
      ) : (
        <View style={{ marginTop: Space.sm, borderBottomWidth: 1, borderBottomColor: c.border, paddingBottom: Space.xs }}>
          <T variant="heading" accessibilityRole="header" style={{ color: c.subheading, fontWeight: "700" }}>
            <Marked text={str(b.text)} marks={marks} bold={bold} />
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
              <Marked text={str(b.text)} marks={marks} bold={bold} />
            </T>
          </View>
        );
      {
        // BOOK-LIST-01: "(a) In electroporation, …" shows its label in a column, the lines hanging beside it.
        const labelled = splitLabel(str(b.text), marks);
        if (labelled)
          return (
            <View style={{ flexDirection: "row", gap: Space.sm }}>
              <T style={{ minWidth: labelled[0].length * LABEL_CH }}>{labelled[0]}</T>
              <T style={{ flex: 1 }}>
                <Marked text={labelled[1]} marks={marks} bold={bold} />
              </T>
            </View>
          );
      }
      return (
        <T>
          <Marked text={str(b.text)} marks={marks} bold={bold} />
        </T>
      );
    case "list":
      return (
        <Lines
          items={strs(b.items)}
          ordered={b.ordered === true}
          marks={marks}
          bold={bold}
          start={typeof b.start === "number" ? b.start : 1}
          continued={b.continued === true}
          marker={isListMarker(b.marker) ? b.marker : undefined}
        />
      );
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
      // BOOK-BOX-01 (READER-STYLE-01 before it): a titled note is one of the book's printed boxes. It keeps the book's
      // look: its title on a header in the colour of its kind and a tinted body, full width on a phone (owner, 2026-10-29).
      if (tone === "note" && title) {
        const head = BOOK_BOX_HEAD[bookBoxKind(title)];
        return (
          <View style={{ borderWidth: 1, borderColor: head, borderRadius: Radius.md, overflow: "hidden", backgroundColor: scheme === "dark" ? c.surfaceMuted : `${head}14` }}>
            <T style={[{ backgroundColor: head, color: "#ffffff", fontWeight: "700", paddingHorizontal: compact ? Space.sm : Space.md, paddingVertical: Space.xs }, compact && SIDE_TEXT]}>
              <Marked text={title} marks={marks} bold={bold} />
            </T>
            <T style={[{ padding: compact ? Space.sm : Space.md }, compact && SIDE_TEXT]}>
              <Marked text={str(b.text)} marks={marks} bold={bold} />
            </T>
          </View>
        );
      }
      // A margin note the book prints without a title: the same tinted box with no header (full width on a phone).
      if (isMarginNote(b))
        return (
          <View style={{ borderWidth: 1, borderColor: MARGIN_NOTE, borderRadius: Radius.md, backgroundColor: scheme === "dark" ? c.surfaceMuted : `${MARGIN_NOTE}1f`, padding: compact ? Space.sm : Space.md }}>
            <T style={compact ? SIDE_TEXT : undefined}>
              <Marked text={str(b.text)} marks={marks} bold={bold} />
            </T>
          </View>
        );
      return (
        <View style={{ borderLeftWidth: 4, borderLeftColor: border, backgroundColor: bg, borderRadius: Radius.md, padding: Space.md, gap: Space.xs }}>
          <T variant="eyebrow" style={{ color: tone === "warning" ? c.warn : tone === "definition" ? c.accent : green ? c.ok : c.muted }}>
            {label}
          </T>
          {title ? (
            <T style={{ fontWeight: "700" }}>
              <Marked text={title} marks={marks} bold={bold} />
            </T>
          ) : null}
          <T>
            <Marked text={str(b.text)} marks={marks} bold={bold} />
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
            <Marked text={str(b.caption)} marks={marks} bold={bold} />
          </T>
          {cards ? (
            cards.map((card, i) => (
              <View key={i} style={{ borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, borderRadius: Radius.md, padding: Space.md, gap: Space.xs }}>
                <T style={{ fontWeight: "700", color: c.accent }}>
                  <Marked text={card.title} marks={marks} bold={bold} />
                </T>
                {card.fields.map((f) => (
                  <View key={f.label} style={{ flexDirection: "row", gap: Space.sm }}>
                    <T variant="small" style={{ width: 104, fontWeight: "600" }}>
                      {f.label}
                    </T>
                    <T style={{ flex: 1 }}>
                      <Marked text={f.value} marks={marks} bold={bold} />
                    </T>
                  </View>
                ))}
              </View>
            ))
          ) : header.length === 1 ? (
            // A one-column table is a boxed list in the book: its items sit in two columns (owner, 2026-10-29).
            <View style={{ borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, borderRadius: Radius.md, overflow: "hidden" }}>
              <T style={{ fontWeight: "700", padding: Space.sm, backgroundColor: c.surfaceMuted }}>
                <Marked text={header[0]} marks={marks} bold={bold} />
              </T>
              <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
                {rows.map((r, i) => (
                  <View key={i} style={{ width: "50%", padding: Space.sm, borderTopWidth: 1, borderColor: c.border }}>
                    <T variant="small">
                      <Marked text={r[0] ?? ""} marks={marks} bold={bold} />
                    </T>
                  </View>
                ))}
              </View>
            </View>
          ) : (
            <Lines items={rows.flat()} ordered={false} marks={marks} bold={bold} />
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
          prompt={(numbered ? splitQuestionNumber(str(b.prompt))?.text : undefined) ?? str(b.prompt)}
          number={numbered ? splitQuestionNumber(str(b.prompt))?.number : undefined}
          options={Array.isArray(b.options) ? (b.options as { id: string; text: string }[]) : []}
          answerId={typeof b.answer_id === "string" ? b.answer_id : null}
          explanation={str(b.explanation)}
          qref={str(b.ref) || undefined}
          steps={Array.isArray(b.steps) ? strs(b.steps).map(stepText) : undefined}
          finalAnswer={str(b.final_answer) || undefined}
          labels={solvedLabels}
          onBook={bookPress(b.book_ref)}
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
            <Marked text={str(b.text_alt)} marks={marks} bold={bold} />
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
            <Marked text={str(b.title)} marks={marks} bold={bold} />
          </T>
          <T>
            <Marked text={str(b.problem)} marks={marks} bold={bold} />
          </T>
          <Lines items={strs(b.steps).map(stepText)} ordered marks={marks} bold={bold} />
          {str(b.answer) ? (
            <T style={{ fontWeight: "600" }}>
              {"Answer: "}
              <Marked text={str(b.answer)} marks={marks} bold={bold} />
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
              <Marked text={str(b.caption)} marks={marks} bold={bold} />
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
          <ArchivedImage id={str(b.asset_version_id)} alt={str(b.alt)} caption={str(b.caption)} assetSource={assetSource} dataSaver={dataSaver} compact={compact} />
          <T variant="small" style={compact ? { fontSize: 12, lineHeight: 16 } : undefined}>
            {str(b.caption)}
          </T>
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
