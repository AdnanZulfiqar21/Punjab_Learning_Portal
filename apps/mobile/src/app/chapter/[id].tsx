import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { TopicNode } from "@portal/contracts";

import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, pageRange } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ChapterScreen() {
  const c = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state, retry } = useRequest((signal) => api.chapter(id, signal), [id]);
  if (state.status === "loading") return <Loading label="Loading chapter" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
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
        <Notice title="Textbook indexed">
          Chapter structure and page references come from the official textbook. Lessons, videos and practice tests appear here
          after academic review.
        </Notice>
        {ch.status !== "complete" && (
          <Notice tone="warn" title={`This chapter is ${ch.status} in the supplied textbook file`}>
            Topics from missing pages are not listed.
          </Notice>
        )}
        <Lessons chapterId={ch.id} />
        <View style={{ gap: Space.sm }}>
          <T variant="heading" accessibilityRole="header">
            Topics
          </T>
          {ch.topics.length === 0 ? (
            <T variant="muted">No topics are recorded for this chapter.</T>
          ) : (
            ch.topics.map((t) => <TopicRow key={t.id} topic={t} />)
          )}
        </View>
        <Card>
          <T variant="heading">In your textbook</T>
          <T variant="muted">Book pages {pageRange(ch.source.printed_start, ch.source.printed_end)}</T>
          <T variant="muted">{ch.visual_count} figures and tables</T>
          <T variant="mono">
            {ch.source.source_id} · PDF pages {pageRange(ch.source.pdf_start, ch.source.pdf_end)}
          </T>
        </Card>
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

function Lessons({ chapterId }: { chapterId: string }) {
  const auth = useAuth();
  if (auth.state.status === "loading") return <T variant="muted">Loading lessons…</T>; // wait for the stored session
  return <LessonList chapterId={chapterId} token={auth.state.status === "signed_in" ? auth.state.token : null} />;
}

function LessonList({ chapterId, token }: { chapterId: string; token: string | null }) {
  const { state, retry } = useRequest((signal) => api.lessons(chapterId, token, signal), [chapterId, token]);
  return (
    <View style={{ gap: Space.sm }}>
      <T variant="heading" accessibilityRole="header">
        Lessons
      </T>
      {state.status === "loading" && <T variant="muted">Loading lessons…</T>}
      {state.status === "error" && (
        <Pressable accessibilityRole="button" onPress={retry}>
          <T variant="muted">Lessons couldn’t load. Tap to try again.</T>
        </Pressable>
      )}
      {state.status === "success" && state.data.length === 0 && (
        <T variant="muted">
          No reviewed lessons are published for this chapter yet. Lessons appear only after an independent subject reviewer
          approves them.
        </T>
      )}
      {state.status === "success" &&
        state.data.map((l) => (
          <Card key={l.id}>
            <T variant="heading" accessibilityRole="header">
              {l.title}
            </T>
            <T variant="small">
              {l.access_tier === "preview" ? "Free preview · " : ""}Reviewed lesson · version {l.version}
            </T>
            <View style={{ marginTop: Space.sm }}>
              {l.locked || !l.body ? (
                <Notice title="Included with a plan or the free 30-day trial">
                  Start your free trial from the Account tab to read this lesson.
                </Notice>
              ) : (
                <LessonBlocks blocks={l.body.blocks as { type: string }[]} />
              )}
            </View>
            <T variant="small" style={{ marginTop: Space.sm }}>
              Textbook pages (PDF):{" "}
              {(l.source_refs as { pdf_from: number; pdf_to: number }[])
                .map((r) => (r.pdf_from === r.pdf_to ? `${r.pdf_from}` : `${r.pdf_from}–${r.pdf_to}`))
                .join(", ")}
            </T>
          </Card>
        ))}
    </View>
  );
}

function TopicRow({ topic, depth = 0 }: { topic: TopicNode; depth?: number }) {
  const c = useTheme();
  const [open, setOpen] = useState(false);
  const expandable = topic.children.length > 0 || topic.points.length > 0;
  return (
    <View style={{ marginLeft: depth * Space.md }}>
      <Pressable
        accessibilityRole={expandable ? "button" : "text"}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
        onPress={() => setOpen((o) => !o)}
        style={{ flexDirection: "row", gap: Space.sm, paddingVertical: Space.sm, borderBottomWidth: 1, borderBottomColor: c.border }}>
        <T variant="mono" style={{ width: 52, color: c.muted }}>
          {topic.number ?? ""}
        </T>
        <T style={{ flex: 1 }}>{topic.title}</T>
        {topic.pdf_page != null && <Badge>PDF p. {topic.pdf_page}</Badge>}
        {expandable && <T variant="muted">{open ? "▾" : "▸"}</T>}
      </Pressable>
      {open && (
        <View style={{ paddingLeft: 60, paddingVertical: Space.xs, gap: Space.xs }}>
          {topic.points.map((p) => (
            <T key={p} variant="small">
              • {p}
            </T>
          ))}
          {topic.children.map((child) => (
            <TopicRow key={child.id} topic={child} depth={1} />
          ))}
        </View>
      )}
    </View>
  );
}
