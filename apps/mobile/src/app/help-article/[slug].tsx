// A published help article on native (P15.S2.T1), rendered with the shared content-block renderer.
import { Stack, useLocalSearchParams } from "expo-router";
import { ScrollView } from "react-native";

import { LessonBlocks } from "@/components/lesson-blocks";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/lib/api";

export default function HelpArticleScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const c = useTheme();
  const req = useRequest((signal) => api.helpArticle(slug, signal), [slug]);
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      <Stack.Screen options={{ title: "Help" }} />
      {req.state.status === "loading" && <Loading label="Loading the article" />}
      {req.state.status === "error" && <ErrorState error={req.state.error} onRetry={req.retry} />}
      {req.state.status === "success" && (
        <>
          <T variant="title">{req.state.data.title}</T>
          {req.state.data.fallback_locale && <Notice title="Shown in English">This article isn&apos;t available in your language yet.</Notice>}
          <LessonBlocks blocks={(req.state.data.body as { blocks: { type: string }[] }).blocks} />
          <T variant="small">Version {req.state.data.version}</T>
        </>
      )}
    </ScrollView>
  );
}
