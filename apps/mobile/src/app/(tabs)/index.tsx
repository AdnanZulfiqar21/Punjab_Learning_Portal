import { router } from "expo-router";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Badge, Card, ErrorState, Loading, T } from "@/components/ui";
import { Space, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";

export default function LearnScreen() {
  const c = useTheme();
  const { state, retry } = useRequest((signal) => api.catalogue(signal), []);
  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      {state.status === "loading" && <Loading label="Loading subjects" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={retry} />}
      {state.status === "success" && (
        <ScrollView contentContainerStyle={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.xl }}>
          <View style={{ gap: Space.xs }}>
            <T variant="title">Learn</T>
            <T variant="muted">Class XI and Class XII use different textbooks and are listed separately.</T>
          </View>
          {state.data.grades.map((g) => (
            <View key={g.grade.id} style={{ gap: Space.sm }} accessibilityRole="list">
              <T variant="heading" accessibilityRole="header">
                {GRADE_LABEL[g.grade.number] ?? g.grade.name}
              </T>
              {g.subjects.map(({ subject, books }) => {
                const book = books[0];
                if (!book) {
                  return (
                    <Card key={subject.id}>
                      <T variant="muted">{subject.name} — no textbook available yet</T>
                    </Card>
                  );
                }
                return (
                  <Card
                    key={subject.id}
                    label={`${GRADE_LABEL[g.grade.number]} ${subject.name}, ${book.chapter_count} ${book.chapter_label.toLowerCase()}s`}
                    onPress={() =>
                      router.push({ pathname: "/book/[grade]/[subject]", params: { grade: String(g.grade.number), subject: subject.code } })
                    }>
                    <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: Space.sm }}>
                      <T style={{ fontWeight: "600", flexShrink: 1 }}>{subject.name}</T>
                      {book.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
                    </View>
                    <T variant="small">
                      {book.chapter_count} {book.chapter_label.toLowerCase()}s
                    </T>
                  </Card>
                );
              })}
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
