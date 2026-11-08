// A formative checkpoint inside a lesson (P07.S1.T3), native. Self-check only: nothing is sent, stored or scored.
import { type ReactNode, useState } from "react";
import { Pressable, Text, View } from "react-native";

import { T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { SOLVED_LABELS_EN, type SolvedLabels } from "@/lib/solved-labels";

type Option = { id: string; text: string };

export function Checkpoint({
  mode,
  prompt,
  options,
  answerId,
  explanation,
  answerFigure,
  revealLabel = "Show what a good answer contains",
  qref,
  steps,
  finalAnswer,
  labels = SOLVED_LABELS_EN,
  onBook,
  number,
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
  /** SOLVED-QUESTION-01: the printed question number ("3(ii)"). */
  qref?: string;
  /** SOLVED-QUESTION-01: the numbered working, shown with the revealed answer. */
  steps?: string[];
  /** SOLVED-QUESTION-01: the answer, set apart from the working. */
  finalAnswer?: string;
  labels?: SolvedLabels;
  /** MCQ-BOOK-LINK-01: opens the book passage this question comes from, highlighted. */
  onBook?: () => void;
  /** QUESTION-NUMBER-01: the question's printed number, drawn apart from its words (`prompt` then has the words). */
  number?: string;
}) {
  const c = useTheme();
  const [chosen, setChosen] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const done = mode === "question" ? chosen !== null : revealed;
  const promptLine = number ? (
    <View style={{ flexDirection: "row", alignItems: "flex-start", gap: Space.sm }}>
      <View
        accessibilityLabel={`${labels.question} ${number}`}
        style={{ minWidth: 32, height: 32, paddingHorizontal: 10, borderRadius: 16, alignItems: "center", justifyContent: "center", backgroundColor: c.accent }}>
        <Text style={{ color: "#ffffff", fontWeight: "700", fontSize: 14, fontVariant: ["tabular-nums"] }}>{number}</Text>
      </View>
      <T style={{ flex: 1, paddingTop: 4 }}>{prompt}</T>
    </View>
  ) : (
    <T>{prompt}</T>
  );
  if (mode === "self_check" && (steps?.length || finalAnswer)) {
    // A book question solved step by step: the question, then (on demand) how to think about it, the numbered
    // working and the final answer, each set apart.
    return (
      <View
        accessibilityLabel={qref ? `${labels.question} ${qref}` : prompt}
        style={{ borderWidth: 1, borderColor: c.accent, backgroundColor: c.surface, borderRadius: Radius.sm, overflow: "hidden" }}>
        <View style={{ gap: Space.sm, backgroundColor: c.accentSoft, padding: Space.md }}>
          {qref ? <T variant="eyebrow" style={{ color: c.accent }}>{`${labels.question} ${qref}`}</T> : null}
          {promptLine}
          <Pressable accessibilityRole="button" aria-expanded={revealed} onPress={() => setRevealed((r) => !r)} style={{ minHeight: 44, justifyContent: "center" }}>
            <Text style={{ color: c.accent, fontWeight: "600" }}>{revealed ? labels.hide : revealLabel}</Text>
          </Pressable>
        </View>
        {revealed ? (
          <View style={{ gap: Space.md, padding: Space.md }}>
            {explanation ? (
              <View style={{ gap: 2, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceMuted, borderRadius: Radius.sm, padding: Space.sm }}>
                <T variant="eyebrow">{labels.think}</T>
                <T variant="small">{explanation}</T>
              </View>
            ) : null}
            {(steps ?? []).map((s, i) => (
              <View key={i} style={{ flexDirection: "row", gap: Space.sm }} accessibilityLabel={`${labels.step} ${i + 1}`}>
                <T style={{ width: 24, textAlign: "right", color: c.accent, fontWeight: "700" }}>{`${i + 1}.`}</T>
                <T style={{ flex: 1 }}>{s}</T>
              </View>
            ))}
            {answerFigure}
            {finalAnswer ? (
              <View style={{ gap: 2, borderWidth: 2, borderColor: c.ok, backgroundColor: c.okSoft, borderRadius: Radius.sm, padding: Space.sm }}>
                <T variant="eyebrow" style={{ color: c.ok }}>{labels.answer}</T>
                <T style={{ fontWeight: "700" }}>{finalAnswer}</T>
              </View>
            ) : null}
          </View>
        ) : null}
      </View>
    );
  }
  return (
    <View accessibilityLabel="Check your understanding" style={{ gap: Space.sm, borderWidth: 1, borderColor: c.accent, backgroundColor: c.accentSoft, borderRadius: Radius.sm, padding: Space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: Space.sm, flexWrap: "wrap" }}>
        <T style={{ fontWeight: "600" }}>Check your understanding</T>
        {onBook ? (
          <Pressable
            accessibilityRole="link"
            accessibilityLabel={labels.book}
            onPress={onBook}
            hitSlop={8}
            style={({ pressed }) => ({
              justifyContent: "center",
              minHeight: 36,
              paddingHorizontal: Space.md,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: c.accent,
              backgroundColor: pressed ? c.accent : c.surface,
            })}>
            {({ pressed }) => <Text style={{ fontSize: 14, fontWeight: "600", color: pressed ? "#ffffff" : c.accent }}>{labels.book}</Text>}
          </Pressable>
        ) : null}
      </View>
      {promptLine}
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
