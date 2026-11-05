// BOOK-EXERCISES-01: a chapter's end-of-chapter exercise, solved, opened from Practice. "English | Roman Urdu" only (no
// lecture), the same lesson renderer and language choice as a topic, and the self-check answers revealed as "Show
// answer" / "Answer dekhein". A language switch returns to the matching block of the other variant (READER-PLACE-01).
// BOOK-PAPERS-01: a Board paper at the end of the book (paper pattern, model paper) opens here too, under its own title.
// VIDEO-SOLUTION-01 (owner, 2026-11-05): a Mathematics exercise adds "Video Solution": every question with its own video
// solution, or "Video not available yet" until its video is added. Worked examples never get one.
import { Redirect, router, Stack, useLocalSearchParams } from "expo-router";
import { useMemo, useRef, useState } from "react";
import { ScrollView, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";

import { LessonBlocks } from "@/components/lesson-blocks";
import { Chip, ErrorState, LinkButton, Loading, Notice, Segmented, T } from "@/components/ui";
import { Space, subjectKey } from "@/constants/theme";
import { useReadingLanguage } from "@/hooks/use-reading-language";
import { useRequest } from "@/hooks/use-request";
import { SubjectAccent, useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, lessonAsset, previewAsset, type TopicReading } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { premiumBook } from "@/lib/book-style";
import { useDisplay } from "@/lib/display";
import { hasVideoSolutions, practiceOnly, practiceTitle, revealLabel } from "@/lib/exercises";
import { plainMath } from "@/lib/inline-math";
import { solvedLabels } from "@/lib/solved-labels";
import { missingLanguageNote, READING_LANGUAGES, type ReadingLanguage } from "@/lib/reading-language-core";
import { mapPlace, placeSignature, type PlaceBlock } from "@/lib/variant-place";

/** The block the reader was on when switching language, kept while the other variant loads. */
type Place = { lessonId: string; index: number; signatures: string[]; target?: number };

export default function ExerciseScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const auth = useAuth();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const { language, choose } = useReadingLanguage();
  const { state, retry } = useRequest((signal) => api.topicLesson(id, token, signal, language), [id, token, language]);
  const placeRef = useRef<Place | null>(null);
  if (auth.state.status === "loading" || state.status === "loading") return <Loading label="Loading exercise" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  // A book topic is read in Learn.
  if (!practiceOnly(state.data.kind)) return <Redirect href={{ pathname: "/topic/[id]", params: { id: state.data.topic_id } }} />;
  return (
    <SubjectAccent subject={state.data.subject_name}>
      <Stack.Screen options={{ title: practiceTitle(state.data), headerBackTitle: "Exercises" }} />
      <Reader reading={state.data} token={token} language={language} onLanguage={choose} placeRef={placeRef} />
    </SubjectAccent>
  );
}

function Reader({
  reading,
  token,
  language,
  onLanguage,
  placeRef,
}: {
  reading: TopicReading;
  token: string | null;
  language: ReadingLanguage;
  onLanguage: (next: ReadingLanguage) => void;
  placeRef: { current: Place | null };
}) {
  const c = useTheme();
  const { dataSaver } = useDisplay().display;
  const lesson = reading.lesson;
  const scroll = useRef<ScrollView>(null);
  const offset = useRef(0);
  const bodyTop = useRef(0);
  const blockYs = useRef<number[]>([]);
  const blocks = useMemo(() => (lesson?.body?.blocks ?? []) as PlaceBlock[], [lesson?.body?.blocks]);
  const signatures = useMemo(() => blocks.map(placeSignature), [blocks]);
  const readable = Boolean(lesson?.body) && !lesson?.locked && reading.availability !== "unavailable";
  const paper = reading.kind === "paper";
  const videoTab = readable && hasVideoSolutions(subjectKey(reading.subject_name), reading.kind);
  const [video, setVideo] = useState(false);
  const questions = blocks.filter((b) => b.type === "checkpoint") as { type: string; ref?: unknown; prompt?: unknown }[];
  const views: readonly (readonly [ReadingLanguage | "video", string])[] = videoTab ? [...READING_LANGUAGES, ["video", "Video Solution"]] : READING_LANGUAGES;

  function switchLanguage(next: ReadingLanguage) {
    if (next === language) return;
    const y = offset.current - bodyTop.current;
    let index = 0;
    blockYs.current.forEach((blockY, i) => {
      if (blockY <= y + 8) index = i;
    });
    placeRef.current = lesson ? { lessonId: lesson.id, index, signatures } : null;
    blockYs.current = [];
    onLanguage(next);
  }
  function onBlockLayout(index: number, y: number) {
    blockYs.current[index] = y;
    const p = placeRef.current;
    if (!p || !lesson || p.lessonId === lesson.id) return;
    p.target ??= mapPlace(p.signatures, signatures, p.index);
    const targetY = blockYs.current[p.target];
    if (targetY !== undefined) {
      placeRef.current = null;
      scroll.current?.scrollTo({ y: bodyTop.current + targetY, animated: false });
    }
  }
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    offset.current = e.nativeEvent.contentOffset.y;
  };
  const note = lesson && readable ? missingLanguageNote(language, lesson.language, lesson.available_languages) : null;
  const back = () => (router.canGoBack() ? router.back() : router.replace("/exercises"));
  return (
    <ScrollView
      ref={scroll}
      onScroll={onScroll}
      scrollEventThrottle={100}
      stickyHeaderIndices={readable ? [0] : undefined}
      stickyHeaderHiddenOnScroll={false}
      style={{ flex: 1, backgroundColor: c.background }}
      contentContainerStyle={{ padding: Space.lg, gap: Space.md }}>
      {readable ? (
        <View style={{ backgroundColor: c.background, paddingBottom: Space.xs }}>
          <Segmented
            label={videoTab ? "Read or watch" : "Exercise language"}
            options={views}
            value={video ? "video" : language}
            onChange={(v) => {
              if (v === "video") return setVideo(true);
              setVideo(false);
              switchLanguage(v);
            }}
          />
        </View>
      ) : null}
      {note && !video ? <T variant="small" accessibilityLiveRegion="polite">{note}</T> : null}
      <View style={{ gap: Space.xs }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
          <T variant="eyebrow">
            {GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`} · {reading.subject_name}
          </T>
          {reading.availability === "private_preview" ? <Chip label="Draft preview: not yet reviewed or published">Draft preview</Chip> : null}
        </View>
        <T variant="title" accessibilityRole="header">
          {practiceTitle(reading)}
        </T>
        <T variant="small">{paper ? "Board model paper" : reading.chapter_title}</T>
      </View>
      {video ? (
        <View style={{ gap: Space.sm }}>
          <Notice title="Video solutions are not available yet">
            Every question of this exercise will get its own video solution, explained step by step. Until a question&apos;s video is added, its worked
            solution is in the English and Roman Urdu views.
          </Notice>
          {questions.map((q, i) => (
            <View key={i} style={{ gap: Space.xs, borderWidth: 1, borderColor: c.border, borderRadius: 12, backgroundColor: c.surface, padding: Space.md }}>
              {typeof q.ref === "string" ? <T variant="eyebrow" style={{ color: c.accent }}>{`Question ${q.ref}`}</T> : null}
              <T>{plainMath(typeof q.prompt === "string" ? q.prompt : "")}</T>
              <T variant="small" accessibilityLiveRegion="polite">
                ▶ Video not available yet
              </T>
            </View>
          ))}
        </View>
      ) : reading.availability === "unavailable" || !lesson?.body ? (
        paper ? (
          <Notice title="This paper isn’t solved here yet">The paper is at the end of your textbook; its worked answers have not been published yet.</Notice>
        ) : (
          <Notice title="This exercise isn’t solved here yet">The chapter&apos;s exercise is in your textbook; its worked answers have not been published yet.</Notice>
        )
      ) : lesson.locked ? (
        <Notice title="Included with a plan or the free 30-day trial">
          Start your free trial from the Account tab to read this {paper ? "paper" : "exercise"}.
        </Notice>
      ) : (
        <View onLayout={(e) => (bodyTop.current = e.nativeEvent.layout.y)}>
          <LessonBlocks
            key={lesson.id}
            blocks={lesson.body.blocks as { type: string }[]}
            assetSource={(versionId) =>
              lesson.private_preview && token ? previewAsset(reading.topic_id, versionId, token) : lessonAsset(lesson.id, versionId, token)
            }
            dataSaver={dataSaver}
            onBlockLayout={onBlockLayout}
            premium={premiumBook(subjectKey(reading.subject_name), reading.grade_number)}
            runnable={lesson.language === "roman_ur"}
            revealLabel={revealLabel(lesson.language)}
            solvedLabels={solvedLabels(lesson.language)}
          />
        </View>
      )}
      <View style={{ borderTopWidth: 1, borderTopColor: c.border, paddingTop: Space.sm }}>
        <LinkButton label="← All book exercises" onPress={back} />
      </View>
    </ScrollView>
  );
}
