// A topic's lesson (pilot): "English | Roman Urdu" at the top, a compact header, the lesson, then previous/next.
// The language choice is kept on this device and, for a signed-in learner, in the profile's explanation language.
// Both variants share one block structure, so switching languages returns to the same place in the lesson.
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useRef } from "react";
import { Pressable, ScrollView, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";

import { LectureView } from "@/components/lecture-view";
import { LessonBlocks } from "@/components/lesson-blocks";
import { CompletionToggle, LessonNote, SaveFormula } from "@/components/lesson-study";
import { Chip, ErrorState, LinkButton, Loading, Notice, Segmented, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { SubjectAccent, useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, lessonAsset, previewAsset, type TopicLecture, type TopicReading } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDisplay } from "@/lib/display";
import { usePrefs } from "@/lib/prefs";
import { missingLanguageNote, preferredLanguage, READING_LANGUAGES, type ReadingLanguage } from "@/lib/reading-language-core";

type Segment = ReadingLanguage | "lecture";
const SEGMENTS: readonly (readonly [Segment, string])[] = [...READING_LANGUAGES, ["lecture", "Lecture"]];

export default function TopicScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const auth = useAuth();
  const { prefs, update } = usePrefs();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const me = auth.state.status === "signed_in" ? auth.state.me : null;
  const language = preferredLanguage(prefs.language, me?.profile?.explanation_language);
  const view = prefs.view === "lecture" ? "lecture" : "read";
  const { state, retry } = useRequest((signal) => api.topicLesson(id, token, signal, language), [id, token, language]);
  const lecture = useRequest((signal) => api.topicLecture(id, token, signal), [id, token]);
  const c = useTheme();

  function choose(next: ReadingLanguage) {
    update({ language: next });
    const p = me?.profile;
    if (token && p?.grade) {
      // Keep the choice with the account too (existing profile service); the device copy already applies.
      void api
        .saveProfile(token, {
          grade: p.grade,
          stream: p.stream ?? null,
          subjects: p.subjects ?? [],
          target_exams: p.target_exams ?? [],
          target_year: p.target_year ?? null,
          explanation_language: next,
          daily_minutes: p.daily_minutes ?? null,
        })
        .then(() => auth.refresh())
        .catch(auth.handleError);
    }
  }

  if (auth.state.status === "loading" || state.status === "loading") return <Loading label="Loading lesson" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  return (
    <SubjectAccent subject={state.data.subject_name}>
      <Stack.Screen options={{ title: state.data.number ?? "Lesson", headerBackTitle: "Chapter" }} />
      <Reader
        reading={state.data}
        token={token}
        language={language}
        view={view}
        lecture={lecture.state.status === "success" ? lecture.state.data : null}
        onLanguage={choose}
        onView={(next) => update({ view: next })}
        background={c.background}
      />
    </SubjectAccent>
  );
}

function Reader({
  reading,
  token,
  language,
  view,
  lecture,
  onLanguage,
  onView,
  background,
}: {
  reading: TopicReading;
  token: string | null;
  language: ReadingLanguage;
  view: "read" | "lecture";
  lecture: TopicLecture | null;
  onLanguage: (next: ReadingLanguage) => void;
  onView: (next: "read" | "lecture") => void;
  background: string;
}) {
  const c = useTheme();
  const lesson = reading.lesson;
  const scroll = useRef<ScrollView>(null);
  const offset = useRef(0);
  const bodyTop = useRef(0);
  const blockYs = useRef<number[]>([]);
  const pending = useRef<number | null>(null);

  // Which block the reader is on, for the language switch (the nearest block that starts above the top of the screen).
  function anchorIndex(): number {
    const y = offset.current - bodyTop.current;
    let index = 0;
    blockYs.current.forEach((blockY, i) => {
      if (blockY <= y + 8) index = i;
    });
    return index;
  }
  function switchLanguage(next: ReadingLanguage) {
    if (next === language) return;
    pending.current = anchorIndex();
    blockYs.current = [];
    onLanguage(next);
  }
  function choose(next: Segment) {
    if (next === "lecture") {
      onView("lecture");
      scroll.current?.scrollTo({ y: 0, animated: false });
      return;
    }
    if (view === "lecture") onView("read");
    switchLanguage(next);
  }
  function onBlockLayout(index: number, y: number) {
    blockYs.current[index] = y;
    if (pending.current === index) {
      pending.current = null;
      scroll.current?.scrollTo({ y: bodyTop.current + y, animated: false });
    }
  }
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    offset.current = e.nativeEvent.contentOffset.y;
  };

  const note = lesson ? missingLanguageNote(language, lesson.language, lesson.available_languages) : null;
  return (
    <ScrollView
      ref={scroll}
      onScroll={onScroll}
      scrollEventThrottle={100}
      stickyHeaderIndices={lesson?.body && !lesson.locked ? [0] : undefined}
      stickyHeaderHiddenOnScroll={false}
      style={{ flex: 1, backgroundColor: background }}
      contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      {lesson?.body && !lesson.locked ? (
        <View style={{ backgroundColor: background, paddingBottom: Space.xs }}>
          <Segmented label="Read or watch" options={SEGMENTS} value={view === "lecture" ? "lecture" : language} onChange={choose} />
        </View>
      ) : null}
      {note && view !== "lecture" ? <T variant="small" accessibilityLiveRegion="polite">{note}</T> : null}
      <View style={{ gap: Space.xs }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
          <Pressable accessibilityRole="button" accessibilityLabel={`Back to chapter ${reading.chapter_number}: ${reading.chapter_title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: reading.chapter_id } })}>
            <T variant="eyebrow">
              {GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`} · {reading.subject_name} · Chapter {reading.chapter_number}
            </T>
          </Pressable>
          {reading.availability === "private_preview" ? <Chip label="Draft preview: not yet reviewed or published">Draft preview</Chip> : null}
        </View>
        <T variant="title" accessibilityRole="header">
          {reading.number ? `${reading.number} ${reading.title}` : reading.title}
        </T>
        <T variant="small">{reading.chapter_title}</T>
      </View>
      {view === "lecture" && lesson?.body && !lesson.locked ? (
        lecture ? <LectureView data={lecture} token={token} /> : <Loading label="Checking for a lecture" />
      ) : null}
      {reading.availability === "unavailable" || !lesson?.body ? (
        <Notice title="This topic’s lesson isn’t ready yet">The chapter outline lists the topic, but its lesson has not been published.</Notice>
      ) : lesson.locked ? (
        <Notice title="Included with a plan or the free 30-day trial">Start your free trial from the Account tab to read this lesson.</Notice>
      ) : (
        <View onLayout={(e) => (bodyTop.current = e.nativeEvent.layout.y)}>
          <LessonBody
            key={lesson.id}
            chapterId={reading.chapter_id}
            topicId={reading.topic_id}
            lessonId={lesson.id}
            token={token}
            privatePreview={lesson.private_preview}
            blocks={lesson.body.blocks as { type: string }[]}
            onBlockLayout={onBlockLayout}
          />
        </View>
      )}
      <View style={{ flexDirection: "row", justifyContent: "space-between", borderTopWidth: 1, borderTopColor: c.border, paddingTop: Space.sm }}>
        {reading.previous_topic_id ? (
          <LinkButton label="← Previous topic" onPress={() => router.replace({ pathname: "/topic/[id]", params: { id: reading.previous_topic_id! } })} />
        ) : (
          <View />
        )}
        {reading.next_topic_id ? <LinkButton label="Next topic →" onPress={() => router.replace({ pathname: "/topic/[id]", params: { id: reading.next_topic_id! } })} /> : null}
      </View>
    </ScrollView>
  );
}

function LessonBody({
  chapterId,
  topicId,
  lessonId,
  token,
  privatePreview,
  blocks,
  onBlockLayout,
}: {
  chapterId: string;
  topicId: string;
  lessonId: string;
  token: string | null;
  privatePreview: boolean;
  blocks: { type: string }[];
  onBlockLayout: (index: number, y: number) => void;
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
    <View style={{ gap: Space.lg }}>
      <LessonBlocks
        blocks={blocks}
        assetSource={(versionId) => (privatePreview && token ? previewAsset(topicId, versionId, token) : lessonAsset(lessonId, versionId, token))}
        dataSaver={dataSaver}
        equationAction={token && study && !privatePreview ? (index) => <SaveFormula token={token} lessonId={lessonId} index={index} /> : undefined}
        onBlockLayout={onBlockLayout}
      />
      {token && !privatePreview ? (
        <View style={{ gap: Space.sm }}>
          <CompletionToggle token={token} lessonId={lessonId} done={done.state.status === "success" && done.state.data.includes(lessonId)} onChange={() => undefined} />
          {study ? <LessonNote token={token} lessonId={lessonId} /> : null}
        </View>
      ) : null}
    </View>
  );
}
