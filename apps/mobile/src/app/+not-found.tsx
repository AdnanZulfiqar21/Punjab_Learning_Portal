// P13.S2.T3: a link to a screen that doesn't exist (an old notice, a mistyped or retired deep link) never strands the
// learner: it says so plainly and offers the way back.
import { router, Stack } from "expo-router";
import { View } from "react-native";

import { Button } from "@/components/form";
import { T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export default function NotFound() {
  const c = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: c.background, padding: Space.lg, justifyContent: "center", gap: Space.md }}>
      <Stack.Screen options={{ title: "Not found" }} />
      <T variant="heading" accessibilityRole="header" style={{ textAlign: "center" }}>
        This page isn&apos;t here
      </T>
      <T variant="muted" style={{ textAlign: "center" }}>
        The link may be old, or the lesson may have moved. Your progress is not affected.
      </T>
      <Button label="Go to Learn" onPress={() => router.navigate("/")} />
    </View>
  );
}
