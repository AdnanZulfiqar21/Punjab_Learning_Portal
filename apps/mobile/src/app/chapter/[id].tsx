import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { TopicNode } from "@portal/contracts";

import { FavouriteStar } from "@/components/lesson-study";
import { OfflinePack } from "@/components/offline-pack";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ChapterScreen() {
  const c = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state, retry } = useRequest((signal) => api.chapter(id, signal), [id]);
  if (state.status === "loading") return <Loading label="Loading chapter" />;
  if (state.status === "error") {
    // P13.S3: offline, a saved copy of this chapter can still be opened.
    return (
      <View style={{ flex: 1, backgroundColor: c.background }}>
        <ErrorState error={state.error} onRetry={retry} />
        {state.error.kind === "offline" && (
          <View style={{ padding: Space.lg }}>
            <Pressable accessibilityRole="button" onPress={() => router.push({ pathname: "/offline/[id]", params: { id } })}>
              <T style={{ color: c.accent, fontWeight: "600", textAlign: "center" }}>Open the saved copy, if you saved one</T>
            </Pressable>
          </View>
        )}
      </View>
    );
  }
  const ch = state.data;
  const bc = ch.breadcrumb;
  return (
    <>
      <Stack.Screen options={{ title: `${bc.chapter_label} ${ch.number}` }} />
      <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
        <View style={{ gap: Space.xs }}>
          <T variant="eyebrow">
            {GRADE_LABEL[bc.grade.number]} · {bc.subject.name} · {bc.chapter_label} {ch.number}
          </T>
          <T variant="title" accessibilityRole="header">
            {ch.title}
          </T>
          {ch.main_concept ? <T variant="muted">{ch.main_concept}</T> : null}
        </View>
        {ch.status !== "complete" && (
          <Notice tone="warn" title={`This chapter is ${ch.status} in the supplied textbook file`}>
            Topics from missing pages are not listed.
          </Notice>
        )}
        <Offline chapterId={ch.id} />
        <View style={{ gap: Space.sm }}>
          <T variant="heading" accessibilityRole="header">
            Topics
          </T>
          {ch.topics.length === 0 ? <T variant="muted">No topics are recorded for this chapter.</T> : <Topics topics={ch.topics} />}
        </View>
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          {ch.previous_chapter_id ? (
            <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: "/chapter/[id]", params: { id: ch.previous_chapter_id! } })}>
              <T style={{ color: c.accent, fontWeight: "600" }}>← Previous</T>
            </Pressable>
          ) : (
            <View />
          )}
          {ch.next_chapter_id ? (
            <Pressable accessibilityRole="button" onPress={() => router.replace({ pathname: "/chapter/[id]", params: { id: ch.next_chapter_id! } })}>
              <T style={{ color: c.accent, fontWeight: "600" }}>Next →</T>
            </Pressable>
          ) : null}
        </View>
      </ScrollView>
    </>
  );
}

function Offline({ chapterId }: { chapterId: string }) {
  const auth = useAuth();
  if (auth.state.status !== "signed_in") return null; // packs belong to an account
  return <OfflinePack token={auth.state.token} owner={auth.state.me.id} chapterId={chapterId} />;
}

function Topics({ topics }: { topics: TopicNode[] }) {
  const auth = useAuth();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const favs = useRequest((signal) => (token ? api.favourites(token, signal) : Promise.resolve([])), [token]);
  const starred = favs.state.status === "success" ? new Set(favs.state.data.map((f) => f.topic_id)) : null;
  return (
    <View>
      {topics.map((t) => (
        <TopicRow key={t.id} topic={t} token={token} starred={token ? starred : null} />
      ))}
    </View>
  );
}

function TopicRow({ topic, depth = 0, token, starred }: { topic: TopicNode; depth?: number; token: string | null; starred: Set<string> | null }) {
  const c = useTheme();
  const [open, setOpen] = useState(false);
  const expandable = topic.children.length > 0 || topic.points.length > 0;
  return (
    <View style={{ marginLeft: depth * Space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, borderBottomWidth: 1, borderBottomColor: c.border }}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={topic.number ? `${topic.number} ${topic.title}` : topic.title}
          onPress={() => router.push({ pathname: "/topic/[id]", params: { id: topic.id } })}
          style={{ flex: 1, flexDirection: "row", gap: Space.sm, paddingVertical: Space.sm }}>
          <T variant="mono" style={{ width: 52, color: c.muted }}>
            {topic.number ?? ""}
          </T>
          <T style={{ flex: 1 }}>{topic.title}</T>
        </Pressable>
        {expandable && (
          <Pressable accessibilityRole="button" accessibilityLabel={`Outline of ${topic.title}`} onPress={() => setOpen((o) => !o)}>
            <T variant="muted">{open ? "Hide outline" : "Outline"}</T>
          </Pressable>
        )}
        {token && starred && (
          <FavouriteStar token={token} topicId={topic.id} label={topic.number ? `${topic.number} ${topic.title}` : topic.title} initial={starred.has(topic.id)} />
        )}
      </View>
      {open && (
        <View style={{ paddingLeft: 60, paddingVertical: Space.xs, gap: Space.xs }}>
          {topic.points.map((p) => (
            <T key={p} variant="small">
              • {p}
            </T>
          ))}
          {topic.children.map((child) => (
            <TopicRow key={child.id} topic={child} depth={1} token={token} starred={starred} />
          ))}
        </View>
      )}
    </View>
  );
}
