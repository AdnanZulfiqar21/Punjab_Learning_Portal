// BOOK-MOCK-01 on the phone (owner, 2026-11-13): Book Mock Test in three tabs, Full book, Half book and Quarter book.
// The student picks a book, then (for a half or a quarter) its part, and sees the numbered tests, as on the web.
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Button } from "@/components/form";
import { TestLink } from "@/components/mock-list";
import { Screen, SubjectTile } from "@/components/premium";
import { Card, ErrorState, Loading, Segmented, T } from "@/components/ui";
import { HeadingFont, Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { SubjectAccent, useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, SUBJECTS } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { bookMocks, partLabel, partsOf, type BookMockKind } from "@/lib/book-mocks";
import { practiceChapters } from "@/lib/exercises";

const TABS: readonly (readonly [BookMockKind, string])[] = [
  ["full", "Full book"],
  ["half", "Half book"],
  ["quarter", "Quarter book"],
];
const PICK: Record<BookMockKind, string> = {
  full: "Each test covers the whole book.",
  half: "Then choose its first or second half.",
  quarter: "Then choose one of its four parts.",
};

export default function BookMocksScreen() {
  const { state } = useAuth();
  const [tab, setTab] = useState<BookMockKind>("half");
  const [book, setBook] = useState<{ subject: string; grade: number } | null>(null);
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  const token = state.status === "signed_in" ? state.token : null;
  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
        <T variant="muted">
          Full Board-pattern papers from the whole book, half of it or a quarter of it. The questions come from every chapter, mixed. Answer the MCQs here,
          write the short and long answers, then check them in the Solution paper.
        </T>
        <Segmented label="Full, half or quarter book mock test" options={TABS} value={tab} onChange={setTab} />
        {book ? (
          <SubjectAccent subject={book.subject}>
            <Book key={`${book.subject}-${book.grade}-${tab}`} tab={tab} token={token} subject={book.subject} grade={book.grade} onBack={() => setBook(null)} />
          </SubjectAccent>
        ) : (
          <Books tab={tab} onPick={(subject, grade) => setBook({ subject, grade })} />
        )}
      </ScrollView>
    </Screen>
  );
}

function Books({ tab, onPick }: { tab: BookMockKind; onPick: (subject: string, grade: number) => void }) {
  const c = useTheme();
  return (
    <View style={{ gap: Space.md }}>
      <View style={{ gap: 2 }}>
        <T variant="subheading" accessibilityRole="header">
          Choose a book
        </T>
        <T variant="muted">{PICK[tab]}</T>
      </View>
      {[11, 12].map((grade) => (
        <View key={grade} style={{ gap: Space.sm }}>
          <Text style={{ fontSize: 12, fontWeight: "700", letterSpacing: 1.5, color: c.muted }}>{GRADE_LABEL[grade].toUpperCase()}</Text>
          {SUBJECTS.map(([code, name]) => {
            const m = bookMocks(code, grade);
            const count = m ? partsOf(m, tab).reduce((a, p) => a + p.tests, 0) : 0;
            return (
              <Pressable
                key={code}
                accessibilityRole="button"
                accessibilityLabel={`${GRADE_LABEL[grade]} ${name}. ${m ? `${count} mock tests` : "Not added yet"}`}
                accessibilityState={{ disabled: !m }}
                disabled={!m}
                onPress={() => onPick(code, grade)}
                style={({ pressed }) => ({
                  flexDirection: "row",
                  alignItems: "center",
                  gap: Space.md,
                  minHeight: 64,
                  padding: Space.md,
                  borderRadius: Radius.xl,
                  borderWidth: 1,
                  borderColor: c.border,
                  backgroundColor: pressed ? c.accentSoft : c.surface,
                  opacity: m ? 1 : 0.6,
                })}>
                <SubjectTile subject={code} size={44} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontFamily: HeadingFont.semibold, fontSize: 16, color: c.text }}>{`${GRADE_LABEL[grade]} ${name}`}</Text>
                  <Text style={{ fontSize: 14, color: c.muted }}>{m ? `${count} mock tests` : "Not added yet"}</Text>
                </View>
                {m ? <Text style={{ fontSize: 22, color: c.muted }}>›</Text> : null}
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

function Book({
  tab,
  token,
  subject,
  grade,
  onBack,
}: {
  tab: BookMockKind;
  token: string | null;
  subject: string;
  grade: number;
  onBack: () => void;
}) {
  const c = useTheme();
  const mocks = bookMocks(subject, grade)!;
  const parts = partsOf(mocks, tab);
  const [key, setKey] = useState(parts[0].key);
  const part = parts.find((p) => p.key === key) ?? parts[0];
  const name = SUBJECTS.find(([code]) => code === subject)?.[1] ?? subject;
  const req = useRequest((signal) => api.bookExercises(grade, subject, token, signal), [grade, subject, token]);
  const data = req.state.status === "success" ? req.state.data : null;
  const label = data?.chapter_label ?? "Chapter";
  const covered = data ? practiceChapters(data).filter((ch) => ch.number >= part.from && ch.number <= part.to) : [];
  return (
    <View style={{ gap: Space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
        <SubjectTile subject={subject} size={44} />
        <View style={{ flex: 1 }}>
          <T variant="subheading" accessibilityRole="header">{`${GRADE_LABEL[grade]} ${name}`}</T>
          <T variant="small" style={{ color: c.muted }}>
            {tab === "full" ? "Full book mock tests." : tab === "half" ? "Half book mock tests: choose a half." : "Quarter book mock tests: choose a part."}
          </T>
        </View>
      </View>
      <View style={{ alignSelf: "flex-start" }}>
        <Button variant="link" label="Choose another book" onPress={onBack} />
      </View>
      {tab !== "full" ? (
        <View accessibilityRole="radiogroup" accessibilityLabel={tab === "half" ? "Which half of the book" : "Which part of the book"} style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.sm }}>
          {parts.map((p) => {
            const on = p.key === part.key;
            return (
              <Pressable
                key={p.key}
                accessibilityRole="radio"
                aria-checked={on}
                onPress={() => setKey(p.key)}
                style={{
                  minHeight: 44,
                  justifyContent: "center",
                  paddingHorizontal: Space.md,
                  borderRadius: Radius.pill,
                  borderWidth: 1,
                  borderColor: on ? c.accent : c.border,
                  backgroundColor: on ? c.accent : c.surface,
                }}>
                <Text style={{ fontWeight: on ? "700" : "500", color: on ? c.onAccent : c.text }}>{partLabel(p, label)}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {req.state.status === "error" ? <ErrorState error={req.state.error} onRetry={req.retry} /> : null}
      {covered.length > 0 ? (
        <T variant="small" style={{ color: c.muted }}>
          {`${tab === "full" ? "The whole book" : partLabel(part, label)}: ${covered.map((ch) => `${ch.number}. ${ch.title}`).join(" · ")}`}
        </T>
      ) : null}
      <Card>
        <View style={{ gap: Space.xs }}>
          {Array.from({ length: part.tests }, (_, k) => k + 1).map((n) => (
            <TestLink
              key={n}
              n={n}
              open
              onPress={() => router.push({ pathname: "/mock-paper", params: { kind: "book", grade: String(grade), subject, part: part.key, n: String(n) } })}
            />
          ))}
        </View>
      </Card>
    </View>
  );
}
