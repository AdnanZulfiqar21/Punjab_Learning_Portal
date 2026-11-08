// BOOK-EXERCISES-01: each chapter's end-of-chapter exercise from the textbook, solved in English and Roman Urdu. Learn
// no longer lists it; Practice opens it here. BOOK-PAPERS-01: the Board papers at the end of the book follow the units.
import type { BookPaper } from "@portal/contracts";
import { router, Stack } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { Choices } from "@/components/form";
import { Screen } from "@/components/premium";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { HeadingFont, Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, SUBJECTS as ALL_SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { exerciseStatus } from "@/lib/exercises";

// The book exercises cover the textbooks the portal teaches; Mathematics is not taught (owner, 2026-10-19).
const SUBJECTS = ALL_SUBJECTS.filter(([code]) => code !== "mathematics");

export default function ExercisesScreen() {
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  const me = state.status === "signed_in" ? state.me : null;
  const subjects = SUBJECTS.map(([code]) => code as string);
  return (
    <Screen>
    <ScrollView contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: "Book exercises" }} />
      <T variant="muted">The exercise at the end of each chapter of your textbook, solved in English and Roman Urdu.</T>
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
  const [grade, setGrade] = useState<11 | 12>(initialGrade);
  const [subject, setSubject] = useState<SubjectCode>(initialSubject);
  const req = useRequest((signal) => api.bookExercises(grade, subject, token, signal), [grade, subject, token]);
  const book = req.state.status === "success" ? req.state.data : null;
  return (
    <View style={{ gap: Space.lg }}>
      <Choices label="Class" options={[[11, GRADE_LABEL[11]], [12, GRADE_LABEL[12]]] as const} selected={[grade]} onToggle={setGrade} />
      <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={setSubject} />
      {req.state.status === "loading" && <Loading label="Loading book exercises" />}
      {req.state.status === "error" && <ErrorState error={req.state.error} onRetry={req.retry} />}
      {book && book.exercises.length === 0 && (
        <Notice title="No book exercises here yet">
          The end-of-chapter exercises of this book are added chapter by chapter. They appear here once they are.
        </Notice>
      )}
      {book && book.exercises.length > 0 && (
        <View style={{ gap: Space.sm }}>
          {book.exercises.map((e) => {
            const status = exerciseStatus(e.availability, e.available_languages);
            const label = `${book.chapter_label} ${e.chapter_number}`;
            return (
              <ExerciseRow
                key={e.topic_id}
                number={String(e.chapter_number)}
                eyebrow={label}
                title={e.chapter_title}
                status={status}
                onPress={() => router.push({ pathname: "/exercise/[id]", params: { id: e.topic_id } })}
              />
            );
          })}
        </View>
      )}
      {book && book.papers.length > 0 ? <Papers papers={book.papers} /> : null}
    </View>
  );
}

/** BOOK-PAPERS-01: the Board's paper pattern and model paper printed at the end of the book, solved. */
function Papers({ papers }: { papers: BookPaper[] }) {
  return (
    <View style={{ gap: Space.sm }}>
      <T variant="heading" accessibilityRole="header">
        Board model paper
      </T>
      {papers.map((p) => {
        const status = exerciseStatus(p.availability, p.available_languages);
        return (
          <ExerciseRow
            key={p.topic_id}
            number="BP"
            eyebrow="Board paper"
            title={p.title}
            status={status}
            onPress={() => router.push({ pathname: "/exercise/[id]", params: { id: p.topic_id } })}
          />
        );
      })}
    </View>
  );
}

/** PREMIUM-MOBILE-01: one exercise as a glass card: the chapter number in a tile, the full title on its own width, and
 * the status as small chips under it (a long status beside the title squeezed it into one word per line). */
function ExerciseRow({
  number,
  eyebrow,
  title,
  status,
  onPress,
}: {
  number: string;
  eyebrow: string;
  title: string;
  status: { label: string; open: boolean };
  onPress: () => void;
}) {
  const c = useTheme();
  const chips = status.label.split(" · ");
  return (
    <Card label={`${eyebrow}: ${title}. ${status.label}`} onPress={status.open ? onPress : undefined} style={!status.open ? { opacity: 0.6 } : undefined}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
        <View style={{ width: 48, height: 48, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: c.accentSoft }}>
          <Text style={{ color: c.accent, fontFamily: HeadingFont.bold, fontSize: number.length > 2 ? 15 : 20 }}>{number}</Text>
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <T variant="small" style={{ color: c.accent, fontWeight: "600" }}>
            {eyebrow}
          </T>
          <T variant="subheading" style={{ fontSize: 17, lineHeight: 22 }}>
            {title}
          </T>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs, marginTop: 2 }}>
            {chips.map((chip) => (
              <View
                key={chip}
                style={{ borderRadius: Radius.pill, paddingHorizontal: Space.sm, paddingVertical: 2, backgroundColor: chip === "Draft preview" ? c.warnSoft : c.surfaceMuted }}>
                <Text style={{ fontSize: 12, fontWeight: "600", color: chip === "Draft preview" ? c.warn : c.muted }}>{chip}</Text>
              </View>
            ))}
          </View>
        </View>
        {status.open ? (
          <T variant="heading" style={{ color: c.accent }} accessibilityElementsHidden>
            ›
          </T>
        ) : null}
      </View>
    </Card>
  );
}
