// PRACTICE-MCQ-01 (owner, 2026-11-08): the portal's own practice questions for every chapter of a book (MCQs now; short
// and long questions later), by book and then chapter as Learn. Not the book's printed exercises: those stay in Book
// exercises ("chapter practice ma book exercises kiu dali hain yaha hum khud pure pure book ka mcqs long short sb banaye ga").
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Choices } from "@/components/form";
import { Screen } from "@/components/premium";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { HeadingFont, Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, SUBJECTS as ALL_SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { exerciseStatus, practiceChapters } from "@/lib/exercises";

const SUBJECTS = ALL_SUBJECTS.filter(([code]) => code !== "mathematics");

export default function ChapterPracticeScreen() {
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  const me = state.status === "signed_in" ? state.me : null;
  const subjects = SUBJECTS.map(([code]) => code as string);
  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
        <T variant="muted">Our own MCQs, short questions and long questions for each chapter of your book, with answers in English and Roman Urdu.</T>
        <List
          token={state.status === "signed_in" ? state.token : null}
          initialGrade={me?.profile?.grade === 12 ? 12 : 11}
          initialSubject={(me?.profile?.subjects?.find((s) => subjects.includes(s)) as SubjectCode | undefined) ?? "computer_science"}
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
  const any = [book?.mcq_sets, book?.short_sets, book?.long_sets].some((s) => (s ?? []).length > 0);
  return (
    <View style={{ gap: Space.lg }}>
      <Choices label="Class" options={[[11, GRADE_LABEL[11]], [12, GRADE_LABEL[12]]] as const} selected={[grade]} onToggle={setGrade} />
      <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={setSubject} />
      {req.state.status === "loading" && <Loading label="Loading chapter practice" />}
      {req.state.status === "error" && <ErrorState error={req.state.error} onRetry={req.retry} />}
      {book && !any && (
        <Notice title="No chapter practice here yet">MCQs, short questions and long questions for this book are added chapter by chapter. They appear here once they are.</Notice>
      )}
      {book && any && (
        <View style={{ gap: Space.md }}>
          {chapters.map((ch) => (
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
                <SetLink kind="MCQs" chapter={`${book.chapter_label} ${ch.number}`} item={ch.mcqs} />
                <SetLink kind="Short questions" chapter={`${book.chapter_label} ${ch.number}`} item={ch.shorts} />
                <SetLink kind="Long questions" chapter={`${book.chapter_label} ${ch.number}`} item={ch.longs} />
              </View>
            </Card>
          ))}
        </View>
      )}
    </View>
  );
}

/** One question set inside a chapter's card ("MCQs"), with its status; a muted line when it isn't added yet. */
function SetLink({
  kind,
  chapter,
  item,
}: {
  kind: string;
  chapter: string;
  item?: { topic_id: string; availability: string; available_languages: readonly string[] };
}) {
  const c = useTheme();
  const status = item ? exerciseStatus(item.availability, item.available_languages) : { label: "Not added yet", open: false };
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${chapter} ${kind}. ${status.label}`}
      accessibilityState={{ disabled: !status.open }}
      disabled={!status.open || !item}
      onPress={() => item && router.push({ pathname: "/exercise/[id]", params: { id: item.topic_id } })}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        gap: Space.md,
        minHeight: 52,
        paddingVertical: Space.sm,
        paddingHorizontal: Space.md,
        borderRadius: Radius.lg,
        backgroundColor: pressed ? c.accentSoft : c.surfaceMuted,
        opacity: status.open ? 1 : 0.6,
      })}>
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={{ fontFamily: HeadingFont.semibold, fontSize: 16, color: c.text }}>{kind}</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs }}>
          {status.label.split(" · ").map((chip) => (
            <View
              key={chip}
              style={{ borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 2, backgroundColor: chip === "Draft preview" ? c.warnSoft : c.surface }}>
              <Text style={{ fontSize: 12, fontWeight: "600", color: chip === "Draft preview" ? c.warn : c.muted }}>{chip}</Text>
            </View>
          ))}
        </View>
      </View>
      {status.open ? <Text style={{ fontSize: 22, color: c.accent }}>›</Text> : null}
    </Pressable>
  );
}
