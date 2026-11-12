// CHAPTER-MOCK-01 / BOOK-MOCK-01 on the phone: one mock test, put together on the device from the chapters' own practice
// sets (MCQs, short and long questions), exactly as the web does (lib/chapter-mocks.ts and lib/book-mocks.ts are the
// same files on both). `kind` "chapter" is a chapter's test n; "book" is test n of a full, half or quarter book.
import { Stack, useLocalSearchParams } from "expo-router";
import { useRef } from "react";
import { ScrollView, View } from "react-native";

import { MockPaper } from "@/components/mock-paper";
import { Screen } from "@/components/premium";
import { Badge, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL, SUBJECTS, type TopicReading } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { bookPart, buildBookPaper, partLabel } from "@/lib/book-mocks";
import { buildPaper, openTests, PATTERNS, type Paper } from "@/lib/chapter-mocks";
import { practiceChapters } from "@/lib/exercises";
import { plainBlocks } from "@/lib/inline-math";

type Blocks = { type: string }[];

const blocksOf = (r: TopicReading): Blocks | null => {
  const lesson = r.lesson as { body?: { blocks?: Blocks } | null; locked?: boolean } | null;
  return lesson?.body?.blocks && !lesson.locked ? lesson.body.blocks : null;
};

export default function MockPaperScreen() {
  const q = useLocalSearchParams<{ kind: string; grade: string; subject: string; chapter?: string; part?: string; n: string }>();
  const { state } = useAuth();
  const token = state.status === "signed_in" ? state.token : null;
  const grade = Number(q.grade);
  const subject = q.subject ?? "";
  const n = Number(q.n);
  const book = q.kind === "book";
  const found = book ? bookPart(subject, grade, q.part ?? "") : undefined;
  const chapter = Number(q.chapter);
  const pattern = PATTERNS[subject];
  const valid =
    !!pattern &&
    Number.isInteger(n) &&
    n >= 1 &&
    (book ? !!found && n <= found.part.tests : openTests(subject, grade, chapter).includes(n));
  const name = SUBJECTS.find(([code]) => code === subject)?.[1] ?? subject;
  const title = `Mock test ${n}`;
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  return (
    <Screen>
      <Stack.Screen options={{ title }} />
      {valid ? (
        <Body
          token={token}
          grade={grade}
          subject={subject}
          name={name}
          n={n}
          from={book ? found!.part.from : chapter}
          to={book ? found!.part.to : chapter}
          build={(sets, label, chTitle) => {
            const paper: Paper = book
              ? buildBookPaper(pattern, found!.part, n, sets)
              : buildPaper(pattern, chapter, n, sets[0]);
            const kindName = !found ? "" : found.kind === "full" ? "Full book" : found.kind === "half" ? "Half book" : "Quarter book";
            const scope = book
              ? found!.kind === "full"
                ? "Full book"
                : `${partLabel(found!.part, label)} (${kindName.toLowerCase()})`
              : `${label} ${chapter}: ${chTitle}`;
            const eyebrow = book ? `${GRADE_LABEL[grade]} ${name} · ${kindName} mock test` : `${GRADE_LABEL[grade]} ${name} · ${label} ${chapter}`;
            const heading = book ? `${title}: ${found!.kind === "full" ? "Full book" : partLabel(found!.part, label)}` : `${title}: ${chTitle}`;
            return { paper: subject === "mathematics" ? plainBlocks(paper) : paper, scope, eyebrow, heading };
          }}
        />
      ) : (
        <View style={{ padding: Space.lg }}>
          <Notice tone="warn" title="This mock test isn't available">
            Go back and choose a mock test from the list.
          </Notice>
        </View>
      )}
    </Screen>
  );
}

function Body({
  token,
  grade,
  subject,
  name,
  n,
  from,
  to,
  build,
}: {
  token: string | null;
  grade: number;
  subject: string;
  name: string;
  n: number;
  from: number;
  to: number;
  build: (
    sets: { mcq: Blocks; short: Blocks; long: Blocks }[],
    label: string,
    chapterTitle: string,
  ) => { paper: Paper; scope: string; eyebrow: string; heading: string };
}) {
  const c = useTheme();
  const scroll = useRef<ScrollView>(null);
  const req = useRequest(
    async (signal) => {
      const bookData = await api.bookExercises(grade, subject, token, signal);
      const chapters = practiceChapters(bookData).filter((ch) => ch.number >= from && ch.number <= to);
      const ready = chapters.length === to - from + 1 && chapters.every((ch) => ch.mcqs && ch.shorts && ch.longs);
      if (!ready) return { ready: false as const };
      const readings = await Promise.all(
        chapters.flatMap((ch) => [ch.mcqs!, ch.shorts!, ch.longs!].map((s) => api.topicLesson(s.topic_id, token, signal))),
      );
      const blocks = readings.map(blocksOf);
      const draft = readings.some((r) => r.availability !== "published");
      if (blocks.some((b) => !b)) return { ready: true as const, locked: true as const, draft };
      const sets = chapters.map((_, i) => ({ mcq: blocks[i * 3]!, short: blocks[i * 3 + 1]!, long: blocks[i * 3 + 2]! }));
      return { ready: true as const, locked: false as const, draft, ...build(sets, bookData.chapter_label, chapters[0].title) };
    },
    [grade, subject, from, to, n, token],
  );
  if (req.state.status === "loading") return <Loading label="Loading the mock test" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const d = req.state.data;
  return (
    <ScrollView ref={scroll} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      {!d.ready ? (
        <Notice tone="warn" title="This mock test isn't ready">
          The chapters&apos; practice questions aren&apos;t all added yet.
        </Notice>
      ) : d.locked ? (
        <Notice title="Sign in to open this mock test">This mock test is still being reviewed. Sign in with a reviewer account to see it.</Notice>
      ) : (
        <>
          <View style={{ gap: Space.xs }}>
            <T variant="small" style={{ color: c.accent, fontWeight: "700", letterSpacing: 1 }}>
              {d.eyebrow.toUpperCase()}
            </T>
            <T variant="title" accessibilityRole="header">
              {d.heading}
            </T>
            <T variant="muted">
              Board paper pattern. Answer the MCQs in the Question paper and submit them; write the short and long answers on paper. The Solution paper shows
              your MCQ result and a model answer for every part.
            </T>
            {d.draft ? (
              <View style={{ alignSelf: "flex-start" }}>
                <Badge>Draft preview · under review</Badge>
              </View>
            ) : null}
          </View>
          <MockPaper
            paper={d.paper}
            head={{
              part: grade === 11 ? "INTERMEDIATE PART-I" : "INTERMEDIATE PART-II",
              className: `Class ${grade === 11 ? "XI" : "XII"}`,
              subject: name.toUpperCase(),
              scope: d.scope,
            }}
            onTop={() => scroll.current?.scrollTo({ y: 0, animated: true })}
          />
        </>
      )}
    </ScrollView>
  );
}
