import { router, Stack, useLocalSearchParams } from "expo-router";
import { FlatList, View } from "react-native";

import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError, GRADE_LABEL, pageRange } from "@/lib/api";

export default function BookScreen() {
  const c = useTheme();
  const { grade, subject } = useLocalSearchParams<{ grade: string; subject: string }>();
  const g = grade === "11" ? 11 : grade === "12" ? 12 : null;
  const { state, retry } = useRequest(
    (signal) => (g ? api.bookFor(g, subject, signal) : Promise.reject(new ApiError("Unknown class.", "not_found"))),
    [g, subject],
  );
  if (state.status === "loading") return <Loading label="Loading chapters" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  const book = state.data;
  const bc = book.breadcrumb;
  return (
    <>
      <Stack.Screen options={{ title: `${GRADE_LABEL[bc.grade.number]} ${bc.subject.name}` }} />
      <FlatList
        style={{ backgroundColor: c.background }}
        contentContainerStyle={{ padding: Space.lg, gap: Space.md }}
        data={book.chapters}
        keyExtractor={(ch) => ch.id}
        ListHeaderComponent={
          <View style={{ gap: Space.md, marginBottom: Space.sm }}>
            <T variant="muted">
              {book.chapters.length} {bc.chapter_label.toLowerCase()}s · textbook source {bc.source_id}
            </T>
            {book.missing_pages.length > 0 && (
              <Notice tone="warn" title="Part of the supplied textbook file is missing">
                {book.missing_pages.join("; ")}
              </Notice>
            )}
          </View>
        }
        renderItem={({ item: ch }) => (
          <Card
            label={`${bc.chapter_label} ${ch.number}: ${ch.title}`}
            onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: ch.id } })}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", gap: Space.sm }}>
              <T variant="small">
                {bc.chapter_label} {ch.number}
                {ch.contents_number != null && ch.contents_number !== ch.number ? ` · Contents: ${ch.contents_number}` : ""}
              </T>
              {ch.status !== "complete" && <Badge tone="warn">{ch.status}</Badge>}
            </View>
            <T style={{ fontWeight: "600" }}>{ch.title}</T>
            <T variant="small">
              {ch.topic_count} topics · {ch.visual_count} figures/tables · book pages {pageRange(ch.printed_start, ch.printed_end)}
            </T>
          </Card>
        )}
      />
    </>
  );
}
