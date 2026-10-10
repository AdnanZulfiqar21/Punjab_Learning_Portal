// A formative checkpoint inside a lesson (P07.S1.T3), native. Self-check only: nothing is sent, stored or scored.
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

type Option = { id: string; text: string };

export function Checkpoint({
  mode,
  prompt,
  options,
  answerId,
  explanation,
}: {
  mode: "question" | "self_check";
  prompt: string;
  options: Option[];
  answerId: string | null;
  explanation: string;
}) {
  const c = useTheme();
  const [chosen, setChosen] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const done = mode === "question" ? chosen !== null : revealed;
  return (
    <View accessibilityLabel="Check your understanding" style={{ gap: Space.sm, borderWidth: 1, borderColor: c.accent, backgroundColor: c.accentSoft, borderRadius: Radius.sm, padding: Space.md }}>
      <T style={{ fontWeight: "600" }}>Check your understanding</T>
      <T>{prompt}</T>
      {mode === "question" ? (
        <View accessibilityRole="radiogroup" style={{ gap: Space.xs }}>
          {options.map((o) => {
            const right = chosen !== null && o.id === answerId;
            return (
              <Pressable
                key={o.id}
                accessibilityRole="radio"
                aria-checked={chosen === o.id}
                disabled={chosen !== null}
                onPress={() => setChosen(o.id)}
                style={{ borderWidth: 1, borderColor: right ? c.accent : c.border, backgroundColor: c.surface, borderRadius: Radius.sm, padding: Space.sm, minHeight: 44 }}>
                <Text style={{ color: c.text, fontWeight: right ? "600" : "400" }}>
                  {o.text}
                  {right ? "  ✓ Correct" : ""}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : (
        !revealed && (
          <Pressable accessibilityRole="button" onPress={() => setRevealed(true)} style={{ minHeight: 44, justifyContent: "center" }}>
            <Text style={{ color: c.accent, fontWeight: "600" }}>Show what a good answer contains</Text>
          </Pressable>
        )
      )}
      {done && (
        <T variant="small" accessibilityLiveRegion="polite">
          {mode === "question" && (chosen === answerId ? "Right. " : "Not quite. ")}
          {explanation}
        </T>
      )}
    </View>
  );
}
