// A chapter (pilot): a compact header, the topics right under it, and offline saving as one quiet row at the end.
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { TopicNode } from "@portal/contracts";

import { FavouriteStar } from "@/components/lesson-study";
import { OfflinePack } from "@/components/offline-pack";
import { ErrorState, LinkButton, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { SubjectAccent, useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { learnTopics } from "@/lib/exercises";

export default function ChapterScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state, retry } = useRequest((signal) => api.chapter(id, signal), [id]);
  const c = useTheme();
  if (state.status === "loading") return <Loading label="Loading chapter" />;
  if (state.status === "error") {
    // P13.S3: offline, a saved copy of this chapter can still be opened.
    return (
      <View style={{ flex: 1, backgroundColor: c.background }}>
        <ErrorState error={state.error} onRetry={retry} />
        {state.error.kind === "offline" && (
          <View style={{ padding: Space.lg, alignItems: "center" }}>
            <LinkButton label="Open the saved copy, if you saved one" onPress={() => router.push({ pathname: "/offline/[id]", params: { id } })} />
          </View>
        )}
      </View>
    );
  }
  const ch = state.data;
  return (
    <SubjectAccent subject={ch.breadcrumb.subject.code}>
      <Stack.Screen options={{ title: `${ch.breadcrumb.chapter_label} ${ch.number}` }} />
      <Chapter ch={ch} />
    </SubjectAccent>
  );
}

function Chapter({ ch }: { ch: Awaited<ReturnType<typeof api.chapter>> }) {
  const c = useTheme();
  const bc = ch.breadcrumb;
  const [intro, setIntro] = useState(false);
  const long = (ch.main_concept ?? "").length > 180;
  const topics = learnTopics(ch.topics); // BOOK-EXERCISES-01: the end-of-chapter exercise is solved in Practice
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <View style={{ gap: Space.xs }}>
        <T variant="eyebrow">
          {GRADE_LABEL[bc.grade.number]} · {bc.subject.name} · {bc.chapter_label} {ch.number}
        </T>
        <T variant="title" accessibilityRole="header">
          {ch.title}
        </T>
        {ch.main_concept ? (
          <View>
            <T variant="muted" numberOfLines={intro || !long ? undefined : 3}>
              {ch.main_concept}
            </T>
            {long ? <LinkButton label={intro ? "Less" : "More"} accessibilityLabel={intro ? "Show less of the introduction" : "Show the whole introduction"} onPress={() => setIntro((o) => !o)} /> : null}
          </View>
        ) : null}
      </View>
      {ch.status !== "complete" && (
        <Notice tone="warn" title={`This chapter is ${ch.status} in the supplied textbook file`}>Topics from missing pages are not listed.</Notice>
      )}
      <View style={{ gap: Space.sm }}>
        <T variant="heading" accessibilityRole="header">
          Topics
        </T>
        {topics.length === 0 ? <T variant="muted">No topics are recorded for this chapter.</T> : <Topics topics={topics} />}
      </View>
      <Offline chapterId={ch.id} />
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        {ch.previous_chapter_id ? (
          <LinkButton label="← Previous chapter" onPress={() => router.replace({ pathname: "/chapter/[id]", params: { id: ch.previous_chapter_id! } })} />
        ) : (
          <View />
        )}
        {ch.next_chapter_id ? <LinkButton label="Next chapter →" onPress={() => router.replace({ pathname: "/chapter/[id]", params: { id: ch.next_chapter_id! } })} /> : null}
      </View>
    </ScrollView>
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
  // Subtopics are always listed under their topic, as the book's contents show them (owner, 2026-10-28); only bullet
  // points fold under "Outline". The contents stay plain: every number in the text colour (owner, 2026-10-28).
  const expandable = topic.points.length > 0;
  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: Space.xs, borderBottomWidth: 1, borderBottomColor: c.border }}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={topic.number ? `${topic.number} ${topic.title}` : topic.title}
          onPress={() => router.push({ pathname: "/topic/[id]", params: { id: topic.id } })}
          style={({ pressed }) => ({ flex: 1, flexDirection: "row", alignItems: "center", gap: Space.sm, paddingVertical: Space.md, minHeight: 52, opacity: pressed ? 0.7 : 1 })}>
          <View style={{ width: depth ? 64 : 48 }}>
            <T variant="eyebrow" style={{ color: c.text }}>
              {topic.number ?? ""}
            </T>
            {/* BOOK-NUMBER-01: where the book misprints the number, its own number to find the page. */}
            {topic.book_number ? (
              <T variant="small" numberOfLines={1} style={{ color: c.muted, fontSize: 10 }}>
                Book# {topic.book_number}
              </T>
            ) : null}
          </View>
          <T style={{ flex: 1, fontWeight: depth ? "400" : "500" }}>{topic.title}</T>
          <T variant="muted" accessibilityElementsHidden>
            ›
          </T>
        </Pressable>
        {expandable && (
          <Pressable accessibilityRole="button" accessibilityLabel={`Outline of ${topic.title}`} onPress={() => setOpen((o) => !o)} style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: Space.xs }}>
            <T variant="small">{open ? "Hide" : "Outline"}</T>
          </Pressable>
        )}
        {token && starred && (
          <FavouriteStar token={token} topicId={topic.id} label={topic.number ? `${topic.number} ${topic.title}` : topic.title} initial={starred.has(topic.id)} />
        )}
      </View>
      {open && (
        <View style={{ paddingLeft: 48, paddingVertical: Space.xs, gap: Space.xs }}>
          {topic.points.map((p) => (
            <T key={p} variant="small">
              • {p}
            </T>
          ))}
        </View>
      )}
      {topic.children.length > 0 && (
        <View style={{ marginLeft: Space.lg, borderLeftWidth: 2, borderLeftColor: c.border, paddingLeft: Space.sm }}>
          {topic.children.map((child) => (
            <TopicRow key={child.id} topic={child} depth={depth + 1} token={token} starred={starred} />
          ))}
        </View>
      )}
    </View>
  );
}
