// A topic's lesson (pilot): "English | Roman Urdu" at the top, a compact header, the lesson, then previous/next.
// The language choice is kept on this device and, for a signed-in learner, in the profile's explanation language.
// The variants differ in structure (the English lesson carries only the book; Roman Urdu adds our explanations), so a
// language switch returns to the matching block of the other variant (READER-PLACE-01, lib/variant-place.ts).
import { Redirect, router, Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Pressable, ScrollView, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";

import { LectureView } from "@/components/lecture-view";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Banner, BannerText } from "@/components/premium";
import { CompletionToggle, LessonNote, SaveFormula } from "@/components/lesson-study";
import { Chip, ErrorState, LinkButton, Loading, Notice, Segmented, T } from "@/components/ui";
import { Space, subjectKey } from "@/constants/theme";
import { useReadingLanguage } from "@/hooks/use-reading-language";
import { useRequest } from "@/hooks/use-request";
import { SubjectAccent, useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, lessonAsset, previewAsset, type TopicLecture, type TopicReading } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { continuesInto, headingOnly, headingTone } from "@/lib/book-heading";
import { premiumBook } from "@/lib/book-style";
import { useDisplay } from "@/lib/display";
import { practiceOnly, revealLabel } from "@/lib/exercises";
import { plainMath } from "@/lib/inline-math";
import { solvedLabels } from "@/lib/solved-labels";
import { usePrefs } from "@/lib/prefs";
import { missingLanguageNote, READING_LANGUAGES, type ReadingLanguage } from "@/lib/reading-language-core";
import { mapPlace, placeSignature, type PlaceBlock } from "@/lib/variant-place";

type Segment = ReadingLanguage | "lecture" | "video";
/** The block the reader was on when switching language, kept by the screen while the other variant loads. */
type Place = { lessonId: string; index: number; signatures: string[]; target?: number };
type Shown = TopicReading & { continued?: TopicReading };
const SEGMENTS: readonly (readonly [Segment, string])[] = [...READING_LANGUAGES, ["lecture", "Lecture"]];

export default function TopicScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const auth = useAuth();
  const { prefs, update } = usePrefs();
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const { language, choose } = useReadingLanguage();
  const view = prefs.view === "lecture" ? "lecture" : "read";
  const { state, retry } = useRequest(async (signal): Promise<Shown> => {
    const reading = await api.topicLesson(id, token, signal, language);
    // BOOK-HEADING-01: the book's heading alone goes on with its first subtopic (lib/book-heading.ts).
    if (!headingOnly(reading) || !reading.next_topic_id) return reading;
    const next = await api.topicLesson(reading.next_topic_id, token, signal, language);
    return continuesInto(reading, next) ? { ...reading, continued: next } : reading;
  }, [id, token, language]);
  const lecture = useRequest((signal) => api.topicLecture(id, token, signal), [id, token]);
  const c = useTheme();
  const placeRef = useRef<Place | null>(null);

  if (auth.state.status === "loading" || state.status === "loading") return <Loading label="Loading lesson" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retry} />;
  // BOOK-EXERCISES-01: the end-of-chapter exercise (and BOOK-PAPERS-01 a Board paper) is solved in Practice; a
  // favourite or a search hit goes there.
  if (practiceOnly(state.data.kind)) return <Redirect href={{ pathname: "/exercise/[id]", params: { id: state.data.topic_id } }} />;
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
        placeRef={placeRef}
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
  placeRef,
}: {
  reading: Shown;
  token: string | null;
  language: ReadingLanguage;
  view: "read" | "lecture";
  lecture: TopicLecture | null;
  onLanguage: (next: ReadingLanguage) => void;
  onView: (next: "read" | "lecture") => void;
  background: string;
  placeRef: RefObject<Place | null>;
}) {
  const c = useTheme();
  const shown = reading.continued ?? reading; // the topic whose lesson is on the screen
  // A heading with nothing to go on with is not a lesson yet.
  const lesson = headingOnly(reading) && !reading.continued ? null : shown.lesson;
  const scroll = useRef<ScrollView>(null);
  const offset = useRef(0);
  const bodyTop = useRef(0);
  const blockYs = useRef<number[]>([]);
  const blocks = useMemo(() => (lesson?.body?.blocks ?? []) as PlaceBlock[], [lesson?.body?.blocks]);
  const signatures = useMemo(() => blocks.map(placeSignature), [blocks]);
  // VIDEO-SOLUTION-01 (owner, 2026-11-05): a Mathematics page has no lecture. Its theory and worked examples have English
  // and Roman Urdu only; an exercise question's page (solved parts with their printed numbers) adds "Video Solution".
  const maths = subjectKey(reading.subject_name) === "mathematics";
  const questions = maths ? (blocks as { type: string; ref?: unknown; prompt?: unknown }[]).filter((b) => b.type === "checkpoint" && typeof b.ref === "string") : [];
  const [video, setVideo] = useState(false);
  const shownView: "read" | "lecture" | "video" = maths ? (video && questions.length > 0 ? "video" : "read") : view;
  const segments: readonly (readonly [Segment, string])[] = maths
    ? questions.length > 0
      ? [...READING_LANGUAGES, ["video", "Video Solution"]]
      : READING_LANGUAGES
    : SEGMENTS;

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
    placeRef.current = lesson ? { lessonId: lesson.id, index: anchorIndex(), signatures } : null;
    blockYs.current = [];
    onLanguage(next);
  }
  function choose(next: Segment) {
    if (next === "video") {
      setVideo(true);
      scroll.current?.scrollTo({ y: 0, animated: false });
      return;
    }
    setVideo(false);
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
          <Segmented
            label={segments.length > READING_LANGUAGES.length ? "Read or watch" : "Explanation language"}
            options={segments}
            value={shownView === "read" ? language : shownView}
            onChange={choose}
          />
        </View>
      ) : null}
      {note && shownView === "read" ? <T variant="small" accessibilityLiveRegion="polite">{note}</T> : null}
      {reading.chapter_start ? (
        // CHAPTER-OPENING-01 (owner-approved for every book, 2026-10-27): the chapter's first topic opens with
        // the chapter itself, its name large in the subject colour on a tinted panel; the topic's own title follows.
        <View style={{ gap: Space.md }}>
          {/* PREMIUM-MOBILE-01: the opening panel is the subject's gradient banner, as on the web (PREMIUM-LOOK-01). */}
          <Banner subject={reading.subject_name}>
            <T aria-hidden importantForAccessibility="no-hide-descendants" style={{ position: "absolute", right: Space.md, bottom: -24, fontSize: 112, lineHeight: 120, fontWeight: "800", color: "#ffffff", opacity: 0.14 }}>
              {reading.chapter_number}
            </T>
            <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
              <Pressable accessibilityRole="button" accessibilityLabel={`Back to chapter ${reading.chapter_number}: ${reading.chapter_title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: reading.chapter_id } })}>
                <BannerText variant="eyebrow">
                  {GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`} · {reading.subject_name}
                </BannerText>
              </Pressable>
              {reading.availability === "private_preview" ? <Chip label="Draft preview: not yet reviewed or published">Draft preview</Chip> : null}
            </View>
            <BannerText variant="eyebrow">{`CHAPTER ${reading.chapter_number}`}</BannerText>
            <BannerText variant="title">{reading.chapter_title}</BannerText>
            <View style={{ height: 4, width: 56, borderRadius: 2, backgroundColor: "rgba(255,255,255,0.8)" }} />
          </Banner>
          <T variant="heading" accessibilityRole="header" style={{ color: toneColor(headingTone(reading.number), c) }}>
            {reading.number ? `${reading.number} ${reading.title}` : reading.title}
          </T>
        </View>
      ) : (
        <View style={{ gap: Space.xs }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
            <Pressable accessibilityRole="button" accessibilityLabel={`Back to chapter ${reading.chapter_number}: ${reading.chapter_title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: reading.chapter_id } })}>
              <T variant="eyebrow">
                {GRADE_LABEL[reading.grade_number] ?? `Class ${reading.grade_number}`} · {reading.subject_name} · Chapter {reading.chapter_number}
              </T>
            </Pressable>
            {reading.availability === "private_preview" ? <Chip label="Draft preview: not yet reviewed or published">Draft preview</Chip> : null}
          </View>
          <T variant="title" accessibilityRole="header" style={{ color: toneColor(headingTone(reading.number), c) }}>
            {reading.number ? `${reading.number} ${reading.title}` : reading.title}
          </T>
          <T variant="small">{reading.chapter_title}</T>
        </View>
      )}
      {shownView === "video" ? (
        <View style={{ gap: Space.sm }}>
          <Notice title="Video solutions are not available yet">
            Every part of this question will get its own video solution, explained step by step. Until its video is added, the worked solution is in
            the English and Roman Urdu views.
          </Notice>
          {questions.map((q, i) => (
            <View key={i} style={{ gap: Space.xs, borderWidth: 1, borderColor: c.border, borderRadius: 12, backgroundColor: c.surface, padding: Space.md }}>
              <T variant="eyebrow" style={{ color: c.accent }}>{`Question ${String(q.ref)}`}</T>
              <T>{plainMath(typeof q.prompt === "string" ? q.prompt : "")}</T>
              <T variant="small" accessibilityLiveRegion="polite">
                ▶ Video not available yet
              </T>
            </View>
          ))}
        </View>
      ) : shownView === "lecture" && lesson?.body && !lesson.locked ? (
        lecture ? <LectureView data={lecture} token={token} /> : <Loading label="Checking for a lecture" />
      ) : reading.availability === "unavailable" || !lesson?.body ? (
        <Notice title="This topic’s lesson isn’t ready yet">The chapter outline lists the topic, but its lesson has not been published.</Notice>
      ) : lesson.locked ? (
        <Notice title="Included with a plan or the free 30-day trial">Start your free trial from the Account tab to read this lesson.</Notice>
      ) : (
        <View onLayout={(e) => (bodyTop.current = e.nativeEvent.layout.y)}>
          {reading.continued ? (
            <T variant="heading" accessibilityRole="header">{`${reading.continued.number} ${reading.continued.title}`}</T>
          ) : null}
          <LessonBody
            key={lesson.id}
            chapterId={reading.chapter_id}
            topicId={shown.topic_id}
            lessonId={lesson.id}
            token={token}
            privatePreview={lesson.private_preview}
            blocks={lesson.body.blocks as { type: string }[]}
            onBlockLayout={onBlockLayout}
            premium={premiumBook(subjectKey(reading.subject_name), reading.grade_number)}
            runnable={lesson.language === "roman_ur"}
            revealLabel={questions.length > 0 ? revealLabel(lesson.language) : undefined}
            solvedLabels={solvedLabels(lesson.language)}
          />
        </View>
      )}
      <View style={{ flexDirection: "row", justifyContent: "space-between", borderTopWidth: 1, borderTopColor: c.border, paddingTop: Space.sm }}>
        {reading.previous_topic_id ? (
          <LinkButton label="← Previous topic" onPress={() => router.replace({ pathname: "/topic/[id]", params: { id: reading.previous_topic_id! } })} />
        ) : (
          <View />
        )}
        {shown.next_topic_id ? <LinkButton label="Next topic →" onPress={() => router.replace({ pathname: "/topic/[id]", params: { id: shown.next_topic_id! } })} /> : null}
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
  premium,
  runnable,
  revealLabel: reveal,
  solvedLabels: labels,
}: {
  chapterId: string;
  topicId: string;
  lessonId: string;
  token: string | null;
  privatePreview: boolean;
  blocks: { type: string }[];
  onBlockLayout: (index: number, y: number) => void;
  premium: boolean;
  runnable: boolean;
  revealLabel?: string;
  solvedLabels?: ReturnType<typeof solvedLabels>;
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
        premium={premium}
        runnable={runnable}
        revealLabel={reveal}
        solvedLabels={labels}
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

/** BOOK-HEADING-01: a heading's colour by its depth (lib/book-heading.ts `headingTone`). */
function toneColor(tone: ReturnType<typeof headingTone>, c: { accent: string; heading: string; subheading: string }): string {
  return tone === "main" ? c.accent : tone === "sub" ? c.subheading : c.heading;
}
