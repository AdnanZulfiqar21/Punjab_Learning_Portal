// BOOK-EXERCISES-01: each chapter's end-of-chapter exercise from the textbook, solved in English and Roman Urdu. Learn
// no longer lists it; Practice opens it here. BOOK-PAPERS-01: the Board papers at the end of the book follow the units.
import type { BookPaper } from "@portal/contracts";
import { router, Stack } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { Choices } from "@/components/form";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, SUBJECTS as ALL_SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { exerciseStatus, exerciseSubjects } from "@/lib/exercises";

// The book exercises cover the textbooks the portal teaches: Mathematics in Class 11 only (MATHS-11-01).

export default function ExercisesScreen() {
  const c = useTheme();
  const { state } = useAuth();
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  const me = state.status === "signed_in" ? state.me : null;
  const initialGrade = me?.profile?.grade === 12 ? 12 : 11;
  const subjects = exerciseSubjects(ALL_SUBJECTS, initialGrade).map(([code]) => code as string);
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: "Book exercises" }} />
      <T variant="muted">The exercises of each chapter of your textbook, solved step by step in English and Roman Urdu.</T>
      <List
        token={state.status === "signed_in" ? state.token : null}
        initialGrade={initialGrade}
        initialSubject={(me?.profile?.subjects?.find((s) => subjects.includes(s)) as SubjectCode | undefined) ?? "computer_science"}
      />
    </ScrollView>
  );
}

function List({ token, initialGrade, initialSubject }: { token: string | null; initialGrade: 11 | 12; initialSubject: SubjectCode }) {
  const c = useTheme();
  const [grade, setGrade] = useState<11 | 12>(initialGrade);
  const [subject, setSubject] = useState<SubjectCode>(initialSubject);
  const SUBJECTS = exerciseSubjects(ALL_SUBJECTS, grade);
  // Class 12 has no Mathematics exercises: switching class from Class 11 Mathematics shows Computer Science.
  const shown: SubjectCode = SUBJECTS.some(([code]) => code === subject) ? subject : "computer_science";
  const req = useRequest((signal) => api.bookExercises(grade, shown, token, signal), [grade, shown, token]);
  const book = req.state.status === "success" ? req.state.data : null;
  return (
    <View style={{ gap: Space.lg }}>
      <Choices label="Class" options={[[11, GRADE_LABEL[11]], [12, GRADE_LABEL[12]]] as const} selected={[grade]} onToggle={setGrade} />
      <Choices label="Subject" options={SUBJECTS} selected={[shown]} onToggle={setSubject} />
      {req.state.status === "loading" && <Loading label="Loading book exercises" />}
      {req.state.status === "error" && <ErrorState error={req.state.error} onRetry={req.retry} />}
      {book && book.exercises.length === 0 && (
        <Notice title="No book exercises here yet">
          The end-of-chapter exercises of this book are added chapter by chapter. They appear here once they are.
        </Notice>
      )}
      {book && book.exercises.length > 0 && (
        <View style={{ gap: Space.xs }}>
          {book.exercises.map((e) => {
            const status = exerciseStatus(e.availability, e.available_languages);
            // MATHS-11-01: a unit that prints several exercises shows each by its own title ("Exercise 1.3").
            const own = /^exercise\s+\d/i.test(e.title);
            const label = own ? `${book.chapter_label} ${e.chapter_number} · ${e.chapter_title}` : `${book.chapter_label} ${e.chapter_number}`;
            const name = own ? e.title : e.chapter_title;
            return (
              <Pressable
                key={e.topic_id}
                accessibilityRole="button"
                accessibilityLabel={`${label}: ${name}. ${status.label}`}
                aria-disabled={!status.open}
                disabled={!status.open}
                onPress={() => router.push({ pathname: "/exercise/[id]", params: { id: e.topic_id } })}
                style={({ pressed }) => ({
                  flexDirection: "row",
                  alignItems: "center",
                  gap: Space.sm,
                  padding: Space.md,
                  minHeight: 52,
                  borderWidth: 1,
                  borderRadius: Radius.sm,
                  borderColor: c.border,
                  backgroundColor: c.surface,
                  opacity: !status.open ? 0.6 : pressed ? 0.7 : 1,
                })}>
                <View style={{ flex: 1, gap: 2 }}>
                  <T variant="eyebrow" style={{ color: c.text }}>
                    {label}
                  </T>
                  <T style={{ fontWeight: "500" }}>{name}</T>
                </View>
                <T variant="small">{status.label}</T>
                {status.open ? (
                  <T variant="muted" accessibilityElementsHidden>
                    ›
                  </T>
                ) : null}
              </Pressable>
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
  const c = useTheme();
  return (
    <View style={{ gap: Space.xs }}>
      <T variant="heading" accessibilityRole="header">
        Board model paper
      </T>
      {papers.map((p) => {
        const status = exerciseStatus(p.availability, p.available_languages);
        return (
          <Pressable
            key={p.topic_id}
            accessibilityRole="button"
            accessibilityLabel={`${p.title}. ${status.label}`}
            aria-disabled={!status.open}
            disabled={!status.open}
            onPress={() => router.push({ pathname: "/exercise/[id]", params: { id: p.topic_id } })}
            style={({ pressed }) => ({
              flexDirection: "row",
              alignItems: "center",
              gap: Space.sm,
              padding: Space.md,
              minHeight: 52,
              borderWidth: 1,
              borderRadius: Radius.sm,
              borderColor: c.border,
              backgroundColor: c.surface,
              opacity: !status.open ? 0.6 : pressed ? 0.7 : 1,
            })}>
            <T style={{ flex: 1, fontWeight: "500" }}>{p.title}</T>
            <T variant="small">{status.label}</T>
            {status.open ? (
              <T variant="muted" accessibilityElementsHidden>
                ›
              </T>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}
