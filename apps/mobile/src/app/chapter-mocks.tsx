// CHAPTER-MOCK-01 on the phone: three Board-pattern mock tests per chapter, by book and then chapter, as on the web.
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { Choices } from "@/components/form";
import { TestLink } from "@/components/mock-list";
import { Screen } from "@/components/premium";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { HeadingFont, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { openTests, TESTS_PER_CHAPTER } from "@/lib/chapter-mocks";
import { practiceChapters } from "@/lib/exercises";

export default function ChapterMocksScreen() {
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  const me = state.status === "signed_in" ? state.me : null;
  const codes = SUBJECTS.map(([code]) => code as string);
  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
        <T variant="muted">
          A full paper for each chapter in the Board pattern: answer the MCQs here, write the short and long answers, then check them in the Solution paper.
        </T>
        <List
          token={state.status === "signed_in" ? state.token : null}
          initialGrade={me?.profile?.grade === 12 ? 12 : 11}
          initialSubject={(me?.profile?.subjects?.find((s) => codes.includes(s)) as SubjectCode | undefined) ?? "physics"}
        />
      </ScrollView>
    </Screen>
  );
}

function List({ token, initialGrade, initialSubject }: { token: string | null; initialGrade: 11 | 12; initialSubject: SubjectCode }) {
  const c = useTheme();
  const [grade, setGrade] = useState<11 | 12>(initialGrade);
  const [subject, setSubject] = useState<SubjectCode>(initialSubject);
  const req = useRequest((signal) => api.bookExercises(grade, subject, token, signal), [grade, subject, token]);
  const book = req.state.status === "success" ? req.state.data : null;
  const chapters = book ? practiceChapters(book) : [];
  const any = chapters.some((ch) => openTests(subject, grade, ch.number).length > 0);
  return (
    <View style={{ gap: Space.lg }}>
      <Choices label="Class" options={[[11, GRADE_LABEL[11]], [12, GRADE_LABEL[12]]] as const} selected={[grade]} onToggle={setGrade} />
      <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={setSubject} />
      {req.state.status === "loading" && <Loading label="Loading mock tests" />}
      {req.state.status === "error" && <ErrorState error={req.state.error} onRetry={req.retry} />}
      {book && !any && <Notice title="No mock tests here yet">Mock tests for this book are added chapter by chapter. They appear here once they are.</Notice>}
      {book &&
        any &&
        chapters.map((ch) => {
          const open = openTests(subject, grade, ch.number);
          return (
            <Card key={ch.number}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
                <View style={{ width: 48, height: 48, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: c.accentSoft }}>
                  <Text style={{ color: c.accent, fontFamily: HeadingFont.bold, fontSize: 20 }}>{ch.number}</Text>
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <T variant="small" style={{ color: c.accent, fontWeight: "600" }}>
                    {`${book.chapter_label} ${ch.number}`}
                  </T>
                  <T variant="subheading" style={{ fontSize: 17, lineHeight: 22 }} accessibilityRole="header">
                    {ch.title}
                  </T>
                </View>
              </View>
              <View style={{ gap: Space.xs, marginTop: Space.sm }}>
                {Array.from({ length: TESTS_PER_CHAPTER }, (_, k) => k + 1).map((n) => (
                  <TestLink
                    key={n}
                    n={n}
                    open={open.includes(n)}
                    onPress={() =>
                      router.push({ pathname: "/mock-paper", params: { kind: "chapter", grade: String(grade), subject, chapter: String(ch.number), n: String(n) } })
                    }
                  />
                ))}
              </View>
            </Card>
          );
        })}
    </View>
  );
}
