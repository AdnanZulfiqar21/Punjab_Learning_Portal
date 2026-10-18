// A `model3d` block on Android/iOS (renderer 2): a labelled poster render first, then a turntable the reader rotates
// by dragging (16 pre-rendered frames, one full turn). No live 3D engine on the phone: the frames are archived asset
// versions like any diagram, so the lesson works offline-saved and under data saver (frames load only when asked).
// Nothing spins on its own, so reduced motion needs no special case.
import { Image } from "expo-image";
import { useEffect, useRef, useState } from "react";
import { PanResponder, Pressable, View, type PanResponderInstance } from "react-native";

import { Chip, LinkButton, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export type AssetSource = (versionId: string) => { uri: string; headers?: Record<string, string> };

const PX_PER_FRAME = 22; // drag distance for one frame step; a full turn is about a screen width

export function Model3D({
  poster,
  frames,
  alt,
  caption,
  labels,
  longDescription,
  assetSource,
  dataSaver,
}: {
  poster: string;
  frames: string[];
  alt: string;
  caption: string;
  labels: string[];
  longDescription: string;
  assetSource?: AssetSource;
  dataSaver?: boolean;
}) {
  const c = useTheme();
  const [mode, setMode] = useState<"poster" | "turntable">("poster");
  const [showPoster, setShowPoster] = useState(!dataSaver);
  const [frame, setFrame] = useState(0);
  const [more, setMore] = useState(false);
  const count = frames.length;
  // What the drag handlers read, kept current after each render; the responder itself is created once, in an effect.
  const live = useRef({ start: 0, frame: 0, count: 0 });
  useEffect(() => {
    live.current.frame = frame;
    live.current.count = count;
  }, [frame, count]);
  const [pan, setPan] = useState<PanResponderInstance | null>(null);
  useEffect(() => {
    const state = live.current;
    setPan(
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dx) > 4 && Math.abs(g.dx) > Math.abs(g.dy),
        onPanResponderGrant: () => {
          state.start = state.frame;
        },
        onPanResponderMove: (_e, g) => {
          if (!state.count) return;
          const step = Math.round(g.dx / PX_PER_FRAME);
          setFrame((((state.start - step) % state.count) + state.count) % state.count); // drag right → model turns right
        },
      }),
    );
  }, []);

  const plate = { backgroundColor: "#ffffff", borderWidth: 1, borderColor: c.border, borderRadius: Radius.md, overflow: "hidden" as const };

  if (!assetSource || !poster) {
    return (
      <View style={{ borderWidth: 1, borderStyle: "dashed", borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.xs }}>
        <T variant="small">{alt}</T>
        {caption ? <T variant="small">{caption}</T> : null}
      </View>
    );
  }

  return (
    <View style={{ gap: Space.sm }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm }}>
        <Chip label="Three-dimensional model">3D model</Chip>
        <T variant="small" style={{ flex: 1 }}>
          {mode === "turntable" ? "Drag left or right to turn it." : "Tap “Rotate” to turn it."}
        </T>
      </View>
      {mode === "poster" ? (
        showPoster ? (
          <View style={plate}>
            <Image source={assetSource(poster)} accessibilityLabel={alt} accessible contentFit="contain" style={{ width: "100%", aspectRatio: 4 / 3 }} />
          </View>
        ) : (
          <View style={{ borderWidth: 1, borderStyle: "dashed", borderColor: c.border, borderRadius: Radius.sm, padding: Space.md, gap: Space.xs }}>
            <T variant="small">{alt}</T>
            <LinkButton label="Show model (data saver is on)" onPress={() => setShowPoster(true)} />
          </View>
        )
      ) : (
        <View
          {...(pan?.panHandlers ?? {})}
          accessible
          accessibilityRole="adjustable"
          accessibilityLabel={`${alt} Turntable, frame ${frame + 1} of ${count}.`}
          accessibilityActions={[
            { name: "increment", label: "Turn right" },
            { name: "decrement", label: "Turn left" },
          ]}
          onAccessibilityAction={(e) => setFrame((f) => (e.nativeEvent.actionName === "increment" ? (f + 1) % count : (f - 1 + count) % count))}
          style={[plate, { aspectRatio: 4 / 3 }]}>
          {frames.map((id, i) => (
            <Image
              key={id}
              source={assetSource(id)}
              contentFit="contain"
              style={{ position: "absolute", left: 0, top: 0, right: 0, bottom: 0, opacity: i === frame ? 1 : 0 }}
            />
          ))}
        </View>
      )}
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md, flexWrap: "wrap" }}>
        {count > 0 && mode === "poster" ? <LinkButton label="Rotate the model" onPress={() => setMode("turntable")} /> : null}
        {mode === "turntable" ? (
          <>
            <Pressable accessibilityRole="button" accessibilityLabel="Turn left" onPress={() => setFrame((f) => (f - 1 + count) % count)} style={{ minHeight: 44, minWidth: 44, justifyContent: "center", alignItems: "center" }}>
              <T style={{ color: c.accent, fontWeight: "700", fontSize: 20 }}>‹</T>
            </Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel="Turn right" onPress={() => setFrame((f) => (f + 1) % count)} style={{ minHeight: 44, minWidth: 44, justifyContent: "center", alignItems: "center" }}>
              <T style={{ color: c.accent, fontWeight: "700", fontSize: 20 }}>›</T>
            </Pressable>
            <LinkButton label="Show labels" onPress={() => setMode("poster")} />
          </>
        ) : null}
      </View>
      {labels.length > 0 && (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs }} accessibilityLabel={`Labels: ${labels.join(", ")}`}>
          {labels.map((l) => (
            <View key={l} style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 2 }}>
              <T variant="small">{l}</T>
            </View>
          ))}
        </View>
      )}
      {caption ? <T variant="small">{caption}</T> : null}
      {longDescription ? (
        <View style={{ gap: Space.xs }}>
          <LinkButton label={more ? "Hide the description" : "Describe this model"} onPress={() => setMore((m) => !m)} />
          {more ? <T variant="muted">{longDescription}</T> : null}
        </View>
      ) : null}
    </View>
  );
}
