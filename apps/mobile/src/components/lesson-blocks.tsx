// Native renderer for content blocks (schema v1, roadmap §5.4). Renderer version 2 on Android/iOS: text blocks render
// natively, comparison tables become cards, and `model3d` blocks show a poster render with a drag-to-rotate turntable.
// An unknown or unsupported block shows its reviewed fallback, or an explicit "update required" note instead of failing.
import { Image } from "expo-image";
import { Fragment, useState, type ReactNode } from "react";
import { View } from "react-native";

import { Checkpoint } from "@/components/checkpoint";
import { Model3D } from "@/components/model3d";
import { LinkButton, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { comparisonCards } from "@/lib/lesson-tables";

export const NATIVE_RENDERER_VERSION = 2;

type Block = { type: string; [key: string]: unknown };
const str = (v: unknown) => (typeof v === "string" ? v : "");
const strs = (v: unknown) => (Array.isArray(v) ? v.map(str) : []);

/** Where an archived asset version can be loaded on this screen (P07.S1.T1): a lesson's own files, with the session. */
export type AssetSource = (versionId: string) => { uri: string; headers?: Record<string, string> };
type Fallback = { text?: unknown; image_asset_id?: unknown; alt?: unknown };

const CALLOUT_LABEL: Record<string, string> = { definition: "Definition", note: "Note", tip: "Tip", warning: "Take care" };

export function LessonBlocks({
  blocks,
  assetSource,
  equationAction,
  dataSaver = false,
  onBlockLayout,
}: {
  blocks: Block[];
  assetSource?: AssetSource;
  /** SETTINGS-01: lesson diagrams load only when tapped (never for questions, where a diagram may be needed). */
  dataSaver?: boolean;
  /** STUDY-TOOLS-01: e.g. "Save formula" under each top-level equation (its index in the lesson body). */
  equationAction?: (index: number) => ReactNode;
  /** Where each block sits (y within this list), so a language switch can return to the same place. */
  onBlockLayout?: (index: number, y: number) => void;
}) {
  return (
    <View style={{ gap: Space.lg }}>
      {blocks.map((b, i) => (
        <Fragment key={i}>
          <View onLayout={onBlockLayout ? (e) => onBlockLayout(i, e.nativeEvent.layout.y) : undefined}>
            <BlockView block={b} assetSource={assetSource} dataSaver={dataSaver} />
          </View>
          {b.type === "equation" && equationAction?.(i)}
        </Fragment>
      ))}
    </View>
  );
}

/** A figure plate: archived PNGs have white backgrounds, so the plate stays white in both themes. */
function ArchivedImage({ id, alt, assetSource, dataSaver }: { id: string; alt: string; assetSource?: AssetSource; dataSaver?: boolean }) {
  const c = useTheme();
  const [shown, setShown] = useState(false);
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
    <View style={{ backgroundColor: "#ffffff", borderWidth: 1, borderColor: c.border, borderRadius: Radius.md, overflow: "hidden" }}>
      <Image source={assetSource(id)} accessibilityLabel={alt} accessible contentFit="contain" style={{ width: "100%", aspectRatio: 4 / 3 }} />
    </View>
  );
}

function Lines({ items, ordered }: { items: string[]; ordered: boolean }) {
  return (
    <View style={{ gap: Space.xs }} accessibilityRole="list">
      {items.map((item, i) => (
        <View key={i} style={{ flexDirection: "row", gap: Space.sm }}>
          <T style={{ width: 22, textAlign: "right" }}>{ordered ? `${i + 1}.` : "•"}</T>
          <T style={{ flex: 1 }}>{item}</T>
        </View>
      ))}
    </View>
  );
}

function BlockView({ block: b, assetSource, dataSaver }: { block: Block; assetSource?: AssetSource; dataSaver?: boolean }) {
  const c = useTheme();
  switch (b.type) {
    case "heading":
      return (
        <T variant={b.level === 3 ? "subheading" : "heading"} accessibilityRole="header" style={{ marginTop: b.level === 3 ? 0 : Space.sm }}>
          {str(b.text)}
        </T>
      );
    case "paragraph":
      return <T>{str(b.text)}</T>;
    case "list":
      return <Lines items={strs(b.items)} ordered={b.ordered === true} />;
    case "callout": {
      const tone = str(b.tone) || "note";
      // A tip is green, as on the web: the diagram explanations ("Understanding the diagram") use it.
      const border = tone === "warning" ? c.warn : tone === "definition" ? c.accent : tone === "tip" ? c.ok : c.border;
      const bg = tone === "warning" ? c.warnSoft : tone === "definition" ? c.accentSoft : tone === "tip" ? c.okSoft : c.surfaceMuted;
      return (
        <View style={{ borderLeftWidth: 4, borderLeftColor: border, backgroundColor: bg, borderRadius: Radius.sm, padding: Space.md, gap: Space.xs }}>
          <T variant="eyebrow" style={{ color: tone === "warning" ? c.warn : tone === "definition" ? c.accent : tone === "tip" ? c.ok : c.muted }}>
            {CALLOUT_LABEL[tone] ?? "Note"}
          </T>
          {str(b.title) ? <T style={{ fontWeight: "600" }}>{str(b.title)}</T> : null}
          <T>{str(b.text)}</T>
        </View>
      );
    }
    case "table": {
      const header = strs(b.header);
      const rows = Array.isArray(b.rows) ? (b.rows as unknown[]).map(strs) : [];
      const cards = comparisonCards(header, rows);
      return (
        <View style={{ gap: Space.sm }} accessibilityLabel={`Table: ${str(b.caption)}`}>
          <T style={{ fontWeight: "600" }}>{str(b.caption)}</T>
          {cards ? (
            cards.map((card, i) => (
              <View key={i} style={{ borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, borderRadius: Radius.md, padding: Space.md, gap: Space.xs }}>
                <T style={{ fontWeight: "700", color: c.accent }}>{card.title}</T>
                {card.fields.map((f) => (
                  <View key={f.label} style={{ flexDirection: "row", gap: Space.sm }}>
                    <T variant="small" style={{ width: 104, fontWeight: "600" }}>
                      {f.label}
                    </T>
                    <T style={{ flex: 1 }}>{f.value}</T>
                  </View>
                ))}
              </View>
            ))
          ) : (
            <Lines items={rows.flat()} ordered={false} />
          )}
        </View>
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
      // Native renderer 2 has no typeset equations: show the reviewed static rendering and the text equivalent (§5.4).
      const fb = (b.fallback ?? {}) as Fallback;
      return (
        <View style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.sm }}>
          {str(fb.image_asset_id) ? <ArchivedImage id={str(fb.image_asset_id)} alt={str(fb.alt) || str(b.text_alt)} assetSource={assetSource} dataSaver={dataSaver} /> : null}
          <T>{str(b.text_alt)}</T>
        </View>
      );
    }
    case "example":
      return (
        <View
          accessibilityLabel={`Worked example: ${str(b.title)}`}
          style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.xs }}>
          <T variant="eyebrow" style={{ color: c.muted }}>
            Worked example
          </T>
          <T style={{ fontWeight: "600" }}>{str(b.title)}</T>
          <T>{str(b.problem)}</T>
          <Lines items={strs(b.steps)} ordered />
          {str(b.answer) ? <T style={{ fontWeight: "600" }}>{`Answer: ${str(b.answer)}`}</T> : null}
        </View>
      );
    case "diagram":
      return (
        <View style={{ gap: Space.xs }}>
          <ArchivedImage id={str(b.asset_version_id)} alt={str(b.alt)} assetSource={assetSource} dataSaver={dataSaver} />
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
