// A formative checkpoint inside a lesson (P07.S1.T3), native. Self-check only: nothing is sent, stored or scored.
import { type ReactNode, useState } from "react";
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
  answerFigure,
  revealLabel = "Show what a good answer contains",
}: {
  mode: "question" | "self_check";
  prompt: string;
  options: Option[];
  answerId: string | null;
  explanation: string;
  /** ANSWER-FIGURE-01: the drawn answer, shown with the explanation once revealed, never before. */
  answerFigure?: ReactNode;
  /** BOOK-EXERCISES-01: the self-check button's words ("Show answer" / "Answer dekhein" on a book exercise). */
  revealLabel?: string;
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
            <Text style={{ color: c.accent, fontWeight: "600" }}>{revealLabel}</Text>
          </Pressable>
        )
      )}
      {/* Text keeps line breaks and leading spaces as written (react-native-web: pre-wrap), so a program in an answer
          keeps its indentation. */}
      {done && (
        <T variant="small" accessibilityLiveRegion="polite">
          {mode === "question" && (chosen === answerId ? "Right. " : "Not quite. ")}
          {explanation}
        </T>
      )}
      {done ? answerFigure : null}
    </View>
  );
}
