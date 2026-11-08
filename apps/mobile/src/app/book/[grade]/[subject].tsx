import { router, Stack, useLocalSearchParams } from "expo-router";
import { FlatList, Text, View } from "react-native";

import { Banner, BannerText, Screen, SubjectTile } from "@/components/premium";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { HeadingFont, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { SubjectAccent, useTheme } from "@/hooks/use-theme";
import { api, ApiError, GRADE_LABEL, pageRange } from "@/lib/api";

export default function BookScreen() {
  const { grade, subject } = useLocalSearchParams<{ grade: string; subject: string }>();
  const g = grade === "11" ? 11 : grade === "12" ? 12 : null;
  const { state, retry } = useRequest(
    (signal) => (g ? api.bookFor(g, subject, signal) : Promise.reject(new ApiError("Unknown class.", "not_found"))),
    [g, subject],
  );
  if (state.status === "loading") return <Loading label="Loading chapters" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  return (
    <SubjectAccent subject={state.data.breadcrumb.subject.code}>
      <Book book={state.data} />
    </SubjectAccent>
  );
}

function Book({ book }: { book: Awaited<ReturnType<typeof api.bookFor>> }) {
  const c = useTheme();
  const bc = book.breadcrumb;
  return (
    <Screen>
      <Stack.Screen options={{ title: `${GRADE_LABEL[bc.grade.number]} ${bc.subject.name}` }} />
      <FlatList
        contentContainerStyle={{ padding: Space.lg, paddingBottom: Space.xxl * 2, gap: Space.md }}
        data={book.chapters}
        keyExtractor={(ch) => ch.id}
        ListHeaderComponent={
          <View style={{ gap: Space.md, marginBottom: Space.sm }}>
            {/* PREMIUM-MOBILE-01: the book's gradient banner with its subject tile */}
            <Banner subject={bc.subject.code}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
                <View style={{ borderRadius: 16, borderWidth: 2, borderColor: "rgba(255,255,255,0.35)" }}>
                  <SubjectTile subject={bc.subject.code} size={52} />
                </View>
                <View style={{ flex: 1 }}>
                  <BannerText variant="eyebrow">{GRADE_LABEL[bc.grade.number]}</BannerText>
                  <BannerText variant="title">{bc.subject.name}</BannerText>
                </View>
              </View>
              <BannerText variant="body">
                {book.chapters.length} {bc.chapter_label.toLowerCase()}s · {book.chapters.reduce((n, ch) => n + ch.topic_count, 0)} topics
              </BannerText>
            </Banner>
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
            <View style={{ flexDirection: "row", alignItems: "center", gap: Space.md }}>
              {/* PREMIUM-MOBILE-01: the chapter number in a tile of the subject's soft accent */}
              <View style={{ width: 48, height: 48, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: c.accentSoft }}>
                <Text style={{ color: c.accent, fontFamily: HeadingFont.bold, fontSize: 20 }}>{ch.number}</Text>
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: Space.sm }}>
                  <T variant="small" style={{ color: c.accent, fontWeight: "600" }}>
                    {bc.chapter_label} {ch.number}
                    {ch.contents_number != null && ch.contents_number !== ch.number ? ` · Contents: ${ch.contents_number}` : ""}
                  </T>
                  {ch.status !== "complete" && <Badge tone="warn">{ch.status}</Badge>}
                </View>
                <T variant="subheading" style={{ fontSize: 17, lineHeight: 22 }}>
                  {ch.title}
                </T>
                <T variant="small">
                  {ch.topic_count} topics · {ch.visual_count} figures/tables · {`book pages ${pageRange(ch.printed_start, ch.printed_end).replace("–", "⁠–⁠")}`}
                </T>
              </View>
            </View>
          </Card>
        )}
      />
    </Screen>
  );
}
