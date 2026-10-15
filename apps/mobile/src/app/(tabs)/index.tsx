import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { Discovery } from "@portal/contracts";

import { DashboardSection } from "@/components/dashboard";
import { Choices } from "@/components/form";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  AVAILABILITY,
  SUBJECTS,
  bookSummary,
  filtersActive,
  type DiscoveryFilters,
} from "@/lib/discovery";

const EMPTY: DiscoveryFilters = {};

export default function LearnScreen() {
  const c = useTheme();
  const auth = useAuth();
  const [filters, setFilters] = useState<DiscoveryFilters>(EMPTY);
  const { state, retry } = useRequest((signal) => api.discovery(filters, signal), [filters]);
  const set = (patch: DiscoveryFilters) => setFilters((current) => ({ ...current, ...patch }));

  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      <ScrollView contentContainerStyle={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.xl }}>
        <View style={{ gap: Space.xs }}>
          <T variant="title">Learn</T>
          <T variant="muted">
            Class XI and Class XII use different textbooks and are listed separately. Each book shows what has been
            reviewed and published so far.
          </T>
        </View>
        {auth.state.status === "signed_in" && <DashboardSection token={auth.state.token} />}
        <View style={{ gap: Space.md }} accessibilityLabel="Filter subjects">
          <Choices
            label="Class"
            options={[
              ["", "Both classes"],
              ["11", "Class XI"],
              ["12", "Class XII"],
            ]}
            selected={[filters.grade ?? ""]}
            onToggle={(value) => set({ grade: value })}
          />
          <Choices
            label="Subject"
            options={[["", "Any subject"], ...SUBJECTS]}
            selected={[filters.subject ?? ""]}
            onToggle={(value) => set({ subject: value })}
          />
          <Choices
            label="Show"
            options={AVAILABILITY}
            selected={[filters.availability ?? "all"]}
            onToggle={(value) => set({ availability: value })}
          />
          {state.status === "success" && (
            <Choices
              label="Track"
              options={[["", "Any track"], ...state.data.tracks.map((t) => [t.code, t.name] as const)]}
              selected={[filters.track ?? ""]}
              onToggle={(value) => set({ track: value })}
            />
          )}
          {state.status === "success" && state.data.exams.length > 0 && (
            <Choices
              label="Exam"
              options={[["", "Any exam"], ...state.data.exams.map((e) => [e.code, `${e.name} ${e.year}`] as const)]}
              selected={[filters.exam ?? ""]}
              onToggle={(value) => set({ exam: value })}
            />
          )}
          {filtersActive(filters) && (
            <Pressable accessibilityRole="button" onPress={() => setFilters(EMPTY)}>
              <T style={{ color: c.accent, fontWeight: "600" }}>Clear filters</T>
            </Pressable>
          )}
        </View>

        {state.status === "loading" && <Loading label="Loading subjects" />}
        {state.status === "error" && <ErrorState error={state.error} onRetry={retry} />}
        {state.status === "success" && <Books data={state.data} filters={filters} />}
      </ScrollView>
    </SafeAreaView>
  );
}

function Books({ data, filters }: { data: Discovery; filters: DiscoveryFilters }) {
  const grades = [11, 12].filter((grade) => data.books.some((book) => book.grade === grade));
  const trackNote = data.tracks.find((track) => track.code === filters.track)?.note;
  return (
    <View style={{ gap: Space.xl }}>
      {data.exams.length === 0 && (
        <T variant="muted">MDCAT and ECAT exam filters appear once their official patterns have been verified.</T>
      )}
      {trackNote ? <T variant="muted">{trackNote}</T> : null}
      {data.books.length === 0 ? (
        <Notice title="Nothing matches these filters yet">Try another class or subject, or clear the filters.</Notice>
      ) : (
        grades.map((grade) => (
          <View key={grade} style={{ gap: Space.sm }} accessibilityRole="list">
            <T variant="heading" accessibilityRole="header">
              {GRADE_LABEL[grade] ?? `Class ${grade}`}
            </T>
            {data.books
              .filter((book) => book.grade === grade)
              .map((book) => (
                <Card
                  key={book.book_id}
                  label={`${GRADE_LABEL[book.grade] ?? ""} ${book.subject_name}, ${book.chapter_count} ${book.chapter_label.toLowerCase()}s`}
                  onPress={() =>
                    router.push({
                      pathname: "/book/[grade]/[subject]",
                      params: { grade: String(book.grade), subject: book.subject },
                    })
                  }>
                  <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: Space.sm }}>
                    <T style={{ fontWeight: "600", flexShrink: 1 }}>{book.subject_name}</T>
                    <View style={{ alignItems: "flex-end", gap: Space.xs }}>
                      {book.state === "not_yet_published" && <Badge>Outline only</Badge>}
                      {book.preview_lessons > 0 && <Badge>Free previews</Badge>}
                      {book.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
                    </View>
                  </View>
                  <T variant="small">
                    {book.chapter_count} {book.chapter_label.toLowerCase()}s · {bookSummary(book)}
                  </T>
                </Card>
              ))}
          </View>
        ))
      )}
      {data.previews.length > 0 && (
        <View style={{ gap: Space.sm }}>
          <T variant="heading" accessibilityRole="header">
            Free preview lessons
          </T>
          <T variant="muted">Reviewed lessons anyone can read, no sign-in needed.</T>
          {data.previews.map((preview) => (
            <Card
              key={preview.lesson_id}
              label={preview.title}
              onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: preview.chapter_id } })}>
              <T style={{ fontWeight: "600" }}>{preview.title}</T>
              <T variant="small">
                {GRADE_LABEL[preview.grade]} {preview.subject_name} · Chapter {preview.chapter_number}
              </T>
            </Card>
          ))}
        </View>
      )}
      <T variant="muted">{data.plans_note}</T>
    </View>
  );
}
