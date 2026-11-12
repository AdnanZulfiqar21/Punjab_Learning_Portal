// The rows of the mock test lists (Chapter mock tests, Book Mock Test).
import { Pressable, Text } from "react-native";

import { HeadingFont, Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

/** "Mock test 2" as a row to open, or muted with "Not added yet". */
export function TestLink({ n, open, onPress }: { n: number; open: boolean; onPress: () => void }) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={open ? `Mock test ${n}` : `Mock test ${n}. Not added yet`}
      accessibilityState={{ disabled: !open }}
      disabled={!open}
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        minHeight: 48,
        paddingHorizontal: Space.md,
        borderRadius: Radius.lg,
        backgroundColor: pressed ? c.accentSoft : c.surfaceMuted,
        opacity: open ? 1 : 0.6,
      })}>
      <Text style={{ fontFamily: HeadingFont.semibold, fontSize: 16, color: c.text }}>{`Mock test ${n}`}</Text>
      {open ? <Text style={{ fontSize: 22, color: c.accent }}>›</Text> : <Text style={{ fontSize: 13, color: c.muted }}>Not added yet</Text>}
    </Pressable>
  );
}
