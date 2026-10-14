import { router, Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { TopicNode } from "@portal/contracts";

import { Choices } from "@/components/form";
import { LessonBlocks } from "@/components/lesson-blocks";
import { CompletionToggle, FavouriteStar, LessonNote, SaveFormula } from "@/components/lesson-study";
import { OfflinePack } from "@/components/offline-pack";
import { Badge, Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, pageRange, lessonAsset } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDisplay } from "@/lib/display";

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
        <Offline chapterId={ch.id} />
        <View style={{ gap: Space.sm }}>
          <T variant="heading" accessibilityRole="header">
            Topics
          </T>
          {ch.topics.length === 0 ? <T variant="muted">No topics are recorded for this chapter.</T> : <Topics topics={ch.topics} />}
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

function Offline({ chapterId }: { chapterId: string }) {
  const auth = useAuth();
  if (auth.state.status !== "signed_in") return null; // packs belong to an account
  return <OfflinePack token={auth.state.token} owner={auth.state.me.id} chapterId={chapterId} />;
}

function Lessons({ chapterId }: { chapterId: string }) {
  const auth = useAuth();
  if (auth.state.status === "loading") return <T variant="muted">Loading lessons…</T>; // wait for the stored session
  return <LessonList chapterId={chapterId} token={auth.state.status === "signed_in" ? auth.state.token : null} />;
}

// P07.S1.T2: each lesson is shown in the chosen language when a reviewed version exists, otherwise in another with a note.
const LANGUAGES = [
  ["en", "English"],
  ["ur", "اردو"],
  ["roman_ur", "Roman Urdu"],
] as const;
type Language = (typeof LANGUAGES)[number][0];
const LANGUAGE_NAME: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };

function LessonList({ chapterId, token }: { chapterId: string; token: string | null }) {
  const { dataSaver } = useDisplay().display; // SETTINGS-01
  // P07.S3.T3 (LESSON-SIZE-01): what a lesson's images and handouts cost to download, before they load.
  const megabytes = (n: number) => (n < 100_000 ? `${Math.max(1, Math.round(n / 1000))} KB` : `${(n / 1_000_000).toFixed(1)} MB`);
  const [language, setLanguage] = useState<Language>("en");
  const { state, retry } = useRequest((signal) => api.lessons(chapterId, token, signal, language), [chapterId, token, language]);
  // LESSON-DONE-01: which lessons this learner marked completed (signed in only).
  const done = useRequest((signal) => (token ? api.completedLessons(token, chapterId, signal) : Promise.resolve([] as string[])), [chapterId, token]);
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const feats = useRequest((signal) => (token ? api.features(token, signal) : Promise.resolve({} as Record<string, boolean>)), [token]);
  const study = feats.state.status === "success" && feats.state.data.study_tools === true; // ROLLOUT-01
  const isDone = (id: string) => toggled[id] ?? (done.state.status === "success" && done.state.data.includes(id));
  // LESSON-PROGRESS-01: where this learner last was in the chapter, from any device (the newest place wins).
  const lastPlace = useRequest((signal) => (token ? api.readingPosition(token, chapterId, signal) : Promise.resolve(null)), [chapterId, token]);
  return (
    <View style={{ gap: Space.sm }}>
      <T variant="heading" accessibilityRole="header">
        Lessons
      </T>
      <Choices label="Language" options={LANGUAGES} selected={[language]} onToggle={setLanguage} />
      {lastPlace.state.status === "success" && lastPlace.state.data ? (
        <T variant="small">You were last reading: {lastPlace.state.data.lesson_title}</T>
      ) : null}
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
            {l.requested_language_missing && (
              <Notice title={`Not available in ${LANGUAGE_NAME[language]} yet`}>Shown in {LANGUAGE_NAME[l.language]}.</Notice>
            )}
            <T variant="heading" accessibilityRole="header" style={l.language === "ur" ? { writingDirection: "rtl", textAlign: "right" } : undefined}>
              {l.title}
            </T>
            <T variant="small">
              {l.access_tier === "preview" ? "Free preview · " : ""}Reviewed lesson · version {l.version}
            </T>
            {!l.locked && (l.download_bytes ?? 0) > 0 ? (
              <T variant="small">
                Images and handouts: {megabytes(l.download_bytes!)}
                {dataSaver ? " · data saver is on, so each loads only when you tap it" : ""}
              </T>
            ) : null}
            <View style={{ marginTop: Space.sm }}>
              {l.locked || !l.body ? (
                <Notice title="Included with a plan or the free 30-day trial">
                  Start your free trial from the Account tab to read this lesson.
                </Notice>
              ) : (
                <View style={l.language === "ur" ? { direction: "rtl" } : undefined}>
                  <LessonBlocks
                    blocks={l.body.blocks as { type: string }[]}
                    assetSource={(v) => lessonAsset(l.id, v, token)}
                    dataSaver={dataSaver}
                    equationAction={token && study ? (i) => <SaveFormula token={token} lessonId={l.id} index={i} /> : undefined}
                  />
                </View>
              )}
            </View>
            {token && !l.locked && l.body ? (
              <View style={{ gap: Space.sm, marginTop: Space.sm }}>
                <CompletionToggle token={token} lessonId={l.id} done={isDone(l.id)} onChange={(d) => setToggled((t) => ({ ...t, [l.id]: d }))} />
                {study && <LessonNote token={token} lessonId={l.id} />}
              </View>
            ) : null}
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

/** Topic outline; signed-in learners can star topics (STUDY-TOOLS-01). */
function Topics({ topics }: { topics: TopicNode[] }) {
  const auth = useAuth();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const favs = useRequest((signal) => (token ? api.favourites(token, signal) : Promise.resolve([])), [token]);
  const starred = favs.state.status === "success" ? new Set(favs.state.data.map((f) => f.topic_id)) : null;
  return (
    <>
      {topics.map((t) => (
        <TopicRow key={t.id} topic={t} token={token} starred={token ? starred : null} />
      ))}
    </>
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
          accessibilityRole={expandable ? "button" : "text"}
          aria-expanded={expandable ? open : undefined}
          disabled={!expandable}
          onPress={() => setOpen((o) => !o)}
          style={{ flex: 1, flexDirection: "row", gap: Space.sm, paddingVertical: Space.sm }}>
          <T variant="mono" style={{ width: 52, color: c.muted }}>
            {topic.number ?? ""}
          </T>
          <T style={{ flex: 1 }}>{topic.title}</T>
          {topic.pdf_page != null && <Badge>PDF p. {topic.pdf_page}</Badge>}
          {expandable && <T variant="muted">{open ? "▾" : "▸"}</T>}
        </Pressable>
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
