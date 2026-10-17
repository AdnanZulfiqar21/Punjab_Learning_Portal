import { router, Stack, useLocalSearchParams } from "expo-router";
import { useEffect } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { LessonBlocks } from "@/components/lesson-blocks";
import { CompletionToggle, LessonNote, SaveFormula } from "@/components/lesson-study";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, lessonAsset, previewAsset } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDisplay } from "@/lib/display";

export default function TopicScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const auth = useAuth();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const { state, retry } = useRequest((signal) => api.topicLesson(id, token, signal), [id, token]);
  const c = useTheme();
  if (auth.state.status === "loading" || state.status === "loading") return <Loading label="Loading lesson" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  const reading = state.data;
  const lesson = reading.lesson;
  return (
    <>
      <Stack.Screen options={{ title: reading.number ?? "Lesson", headerBackTitle: "Chapter" }} />
      <ScrollView style={{ flex: 1, backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
        <Pressable accessibilityRole="button" onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: reading.chapter_id } })}>
          <T variant="eyebrow" style={{ color: c.accent }}>
            {GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`} · {reading.subject_name} · Chapter {reading.chapter_number}
          </T>
        </Pressable>
        <T variant="title" accessibilityRole="header">
          {reading.number ? `${reading.number} ${reading.title}` : reading.title}
        </T>
        <T variant="muted">{reading.chapter_title}</T>
        {reading.availability === "private_preview" && (
          <Notice title="Private draft">
            This lesson is not published. Only staff who cover this subject can read it. Your place in the chapter is saved after publication.
          </Notice>
        )}
        {reading.availability === "unavailable" || !lesson?.body ? (
          <T>This lesson is not ready yet. An outline is not the lesson.</T>
        ) : lesson.locked ? (
          <Notice title="Included with a plan or the free 30-day trial">Start your free trial from the Account tab to read this lesson.</Notice>
        ) : (
          <LessonBody
            chapterId={reading.chapter_id}
            topicId={reading.topic_id}
            lessonId={lesson.id}
            token={token}
            privatePreview={lesson.private_preview}
            blocks={lesson.body.blocks as { type: string }[]}
          />
        )}
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          {reading.previous_topic_id ? (
            <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: "/topic/[id]", params: { id: reading.previous_topic_id! } })}>
              <T style={{ color: c.accent, fontWeight: "600" }}>Previous topic</T>
            </Pressable>
          ) : (
            <View />
          )}
          {reading.next_topic_id ? (
            <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: "/topic/[id]", params: { id: reading.next_topic_id! } })}>
              <T style={{ color: c.accent, fontWeight: "600" }}>Next topic</T>
            </Pressable>
          ) : null}
        </View>
      </ScrollView>
    </>
  );
}

function LessonBody({
  chapterId,
  topicId,
  lessonId,
  token,
  privatePreview,
  blocks,
}: {
  chapterId: string;
  topicId: string;
  lessonId: string;
  token: string | null;
  privatePreview: boolean;
  blocks: { type: string }[];
}) {
  const { dataSaver } = useDisplay().display;
  useEffect(() => {
    // Published lessons only. A draft is not a live lesson, so it must not write reading progress.
    if (token && !privatePreview) void api.saveReadingPosition(token, lessonId).catch(() => undefined);
  }, [token, privatePreview, lessonId]);
  const feats = useRequest((signal) => (token ? api.features(token, signal) : Promise.resolve({} as Record<string, boolean>)), [token]);
  const study = feats.state.status === "success" && feats.state.data.study_tools === true;
  const done = useRequest(
    (signal) => (token && !privatePreview ? api.completedLessons(token, chapterId, signal) : Promise.resolve([] as string[])),
    [token, privatePreview, chapterId],
  );
  return (
    <View style={{ gap: Space.md }}>
      <LessonBlocks
        blocks={blocks}
        assetSource={(versionId) =>
          privatePreview && token ? previewAsset(topicId, versionId, token) : lessonAsset(lessonId, versionId, token)
        }
        dataSaver={dataSaver}
        equationAction={token && study && !privatePreview ? (index) => <SaveFormula token={token} lessonId={lessonId} index={index} /> : undefined}
      />
      {token && !privatePreview ? (
        <View style={{ gap: Space.sm }}>
          <CompletionToggle
            token={token}
            lessonId={lessonId}
            done={done.state.status === "success" && done.state.data.includes(lessonId)}
            onChange={() => undefined}
          />
          {study ? <LessonNote token={token} lessonId={lessonId} /> : null}
        </View>
      ) : null}
    </View>
  );
}
