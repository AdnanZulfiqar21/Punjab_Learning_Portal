// Native renderer for content blocks (schema v1, roadmap §5.4). Renderer version 1 on Android/iOS: text blocks render
// natively; an unknown or unsupported block shows an explicit "update required" note instead of failing.
import { ScrollView, View } from "react-native";

import { Checkpoint } from "@/components/checkpoint";
import { T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export const NATIVE_RENDERER_VERSION = 1;

type Block = { type: string; [key: string]: unknown };
const str = (v: unknown) => (typeof v === "string" ? v : "");
const strs = (v: unknown) => (Array.isArray(v) ? v.map(str) : []);

export function LessonBlocks({ blocks }: { blocks: Block[] }) {
  return (
    <View style={{ gap: Space.md }}>
      {blocks.map((b, i) => (
        <BlockView key={i} block={b} />
      ))}
    </View>
  );
}

function BlockView({ block: b }: { block: Block }) {
  const c = useTheme();
  switch (b.type) {
    case "heading":
      return (
        <T variant="heading" accessibilityRole="header" style={b.level === 3 ? { fontSize: 16 } : undefined}>
          {str(b.text)}
        </T>
      );
    case "paragraph":
      return <T>{str(b.text)}</T>;
    case "list":
      return (
        <View style={{ gap: Space.xs }} accessibilityRole="list">
          {strs(b.items).map((item, i) => (
            <View key={i} style={{ flexDirection: "row", gap: Space.sm }}>
              <T style={{ width: 22, textAlign: "right" }}>{b.ordered ? `${i + 1}.` : "•"}</T>
              <T style={{ flex: 1 }}>{item}</T>
            </View>
          ))}
        </View>
      );
    case "callout": {
      const tone = str(b.tone) || "note";
      const border = tone === "warning" ? c.warn : tone === "definition" ? c.accent : c.border;
      const bg = tone === "warning" ? c.warnSoft : tone === "definition" ? c.accentSoft : c.surfaceMuted;
      return (
        <View style={{ borderLeftWidth: 4, borderLeftColor: border, backgroundColor: bg, borderRadius: Radius.sm, padding: Space.md, gap: Space.xs }}>
          <T variant="eyebrow" style={{ color: c.muted, textTransform: "uppercase" }}>
            {tone}
          </T>
          {str(b.title) ? <T style={{ fontWeight: "600" }}>{str(b.title)}</T> : null}
          <T>{str(b.text)}</T>
        </View>
      );
    }
    case "table": {
      const header = strs(b.header);
      const rows = Array.isArray(b.rows) ? (b.rows as unknown[]).map(strs) : [];
      const cell = { borderWidth: 1, borderColor: c.border, padding: Space.sm, minWidth: 110 } as const;
      return (
        <View style={{ gap: Space.xs }}>
          <T style={{ fontWeight: "600" }}>{str(b.caption)}</T>
          <ScrollView horizontal accessibilityLabel={`Table: ${str(b.caption)}`}>
            <View>
              <View style={{ flexDirection: "row", backgroundColor: c.surfaceMuted }}>
                {header.map((h, i) => (
                  <T key={i} style={[cell, { fontWeight: "600" }]}>
                    {h}
                  </T>
                ))}
              </View>
              {rows.map((r, i) => (
                <View key={i} style={{ flexDirection: "row" }}>
                  {r.map((v, j) => (
                    <T key={j} style={cell}>
                      {v}
                    </T>
                  ))}
                </View>
              ))}
            </View>
          </ScrollView>
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
    case "equation":
      // Native renderer 1 has no typeset equations; published lessons carry a reviewed text equivalent (§5.4).
      return (
        <View style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, padding: Space.md }}>
          <T>{str(b.text_alt)}</T>
        </View>
      );
    default:
      return (
        <View accessibilityRole="alert" style={{ backgroundColor: c.warnSoft, borderRadius: Radius.sm, padding: Space.md }}>
          <T variant="small">This part of the lesson needs a newer version of the app to display.</T>
        </View>
      );
  }
}
