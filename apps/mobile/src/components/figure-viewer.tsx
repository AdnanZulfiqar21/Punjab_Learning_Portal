// DIAGRAM-ZOOM-01: a lesson figure full screen, so its labels can be read on a phone. Pinch with two fingers to zoom
// (up to 5 times), drag to move while zoomed, double-tap to zoom in on a point or back out. The - / Reset / + buttons do
// the same for anyone who can't pinch. The figure keeps its white plate; the bars around it stay dark in both themes.
import { Image } from "expo-image";
import { Modal, Pressable, View, type LayoutChangeEvent } from "react-native";
import { Gesture, GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useReducedMotion } from "@/lib/display";
import { clampView, panTo, pinchTo, stepZoom, toggleZoom, WHOLE, type Box, type ZoomView } from "@/lib/zoom";

const BAR = "#111317";
const BAR_TEXT = "#e5e7eb";
const BAR_MUTED = "#cbd5e1";

export function FigureViewer({
  source,
  alt,
  caption,
  onClose,
}: {
  source: { uri: string; headers?: Record<string, string> };
  alt: string;
  caption?: string;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  const still = useReducedMotion();
  const duration = still ? 0 : 180;
  const width = useSharedValue(1);
  const height = useSharedValue(1);
  const scale = useSharedValue(1);
  const x = useSharedValue(0);
  const y = useSharedValue(0);
  const start = useSharedValue<ZoomView>(WHOLE);
  // Where the view is heading: the buttons step from here, so quick presses add up even while an animation runs.
  const goal = useSharedValue<ZoomView>(WHOLE);

  const box = (): Box => {
    "worklet";
    return { width: width.value, height: height.value };
  };
  const now = (): ZoomView => {
    "worklet";
    return { scale: scale.value, x: x.value, y: y.value };
  };
  const show = (v: ZoomView, animate: boolean) => {
    "worklet";
    goal.value = v;
    scale.value = animate ? withTiming(v.scale, { duration }) : v.scale;
    x.value = animate ? withTiming(v.x, { duration }) : v.x;
    y.value = animate ? withTiming(v.y, { duration }) : v.y;
  };

  const pinch = Gesture.Pinch()
    .onStart(() => {
      start.value = now();
    })
    .onUpdate((e) => {
      show(pinchTo(box(), start.value, e.scale, e.focalX, e.focalY), false);
    })
    .onEnd(() => {
      show(clampView(box(), now()), true);
    });
  const pan = Gesture.Pan()
    .maxPointers(1)
    .onStart(() => {
      start.value = now();
    })
    .onUpdate((e) => {
      show(panTo(start.value, e.translationX, e.translationY), false);
    })
    .onEnd(() => {
      show(clampView(box(), now()), true);
    });
  const doubleTap = Gesture.Tap()
    .numberOfTaps(2)
    .onEnd((e) => {
      show(toggleZoom(box(), now(), e.x, e.y), true);
    });
  const gesture = Gesture.Race(doubleTap, Gesture.Simultaneous(pinch, pan));

  const figure = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }, { translateY: y.value }, { scale: scale.value }] }));
  const onLayout = (e: LayoutChangeEvent) => {
    width.value = e.nativeEvent.layout.width;
    height.value = e.nativeEvent.layout.height;
    show(WHOLE, false);
  };

  return (
    <Modal visible animationType={still ? "none" : "fade"} presentationStyle="fullScreen" onRequestClose={onClose} statusBarTranslucent>
      <GestureHandlerRootView style={{ flex: 1, backgroundColor: BAR }}>
        <View style={{ paddingTop: insets.top + Space.sm, paddingBottom: Space.sm, paddingHorizontal: Space.lg, flexDirection: "row", alignItems: "center", gap: Space.md }}>
          <T variant="small" numberOfLines={3} style={{ flex: 1, color: BAR_TEXT }}>
            {caption || alt}
          </T>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close the diagram"
            onPress={onClose}
            hitSlop={12}
            style={{ paddingHorizontal: Space.md, paddingVertical: Space.sm, borderRadius: Radius.pill, backgroundColor: "#2a2e35" }}>
            <T style={{ color: "#ffffff", fontWeight: "700" }}>Close</T>
          </Pressable>
        </View>
        <GestureDetector gesture={gesture}>
          <View style={{ flex: 1, overflow: "hidden", backgroundColor: "#ffffff" }} onLayout={onLayout} accessible accessibilityRole="image" accessibilityLabel={alt}>
            <Animated.View style={[{ flex: 1 }, figure]}>
              <Image source={source} contentFit="contain" style={{ flex: 1 }} accessibilityIgnoresInvertColors />
            </Animated.View>
          </View>
        </GestureDetector>
        <View style={{ paddingTop: Space.sm, paddingBottom: insets.bottom + Space.sm, paddingHorizontal: Space.lg, alignItems: "center", gap: Space.sm }}>
          <T variant="small" style={{ color: BAR_MUTED, textAlign: "center" }}>
            Pinch with two fingers to zoom, drag to move, double-tap to zoom in or out.
          </T>
          <View style={{ flexDirection: "row", gap: Space.md }}>
            <ZoomButton label="−" accessibilityLabel="Zoom out" onPress={() => show(stepZoom(box(), goal.value, -1), true)} />
            <ZoomButton label="Reset" accessibilityLabel="Show the whole diagram" onPress={() => show(WHOLE, true)} />
            <ZoomButton label="+" accessibilityLabel="Zoom in" onPress={() => show(stepZoom(box(), goal.value, 1), true)} />
          </View>
        </View>
      </GestureHandlerRootView>
    </Modal>
  );
}

function ZoomButton({ label, accessibilityLabel, onPress }: { label: string; accessibilityLabel: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={onPress}
      hitSlop={8}
      style={{ minWidth: 64, minHeight: 44, alignItems: "center", justifyContent: "center", paddingHorizontal: Space.md, borderRadius: Radius.pill, backgroundColor: "#2a2e35" }}>
      <T style={{ color: "#ffffff", fontWeight: "700", fontSize: label.length === 1 ? 22 : 16 }}>{label}</T>
    </Pressable>
  );
}
