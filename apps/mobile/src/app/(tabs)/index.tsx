// Learn (pilot): choose class, then study group; the books for that class and group; "Continue reading" only when a
// real reading position exists. A signed-in learner's profile sets the context; a guest's choice stays on this device.
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { Discovery, Me, ProfileInput } from "@portal/contracts";

import { LearnContextPicker } from "@/components/learn-context-picker";
import { Badge, Card, ErrorState, LinkButton, Loading, Notice, T } from "@/components/ui";
import { Space, SubjectAccents, subjectKey, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useScheme, useTheme } from "@/hooks/use-theme";
import { api, GRADE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { bookSummary } from "@/lib/discovery";
import { contextLine, resolveContext, STREAMS, type LearnContext } from "@/lib/learn-context-core";
import { usePrefs } from "@/lib/prefs";

export default function LearnScreen() {
  const c = useTheme();
  const auth = useAuth();
  const { prefs, loaded, update } = usePrefs();
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState<"profile" | "device" | null>(null);
  const me = auth.state.status === "signed_in" ? auth.state.me : null;
  const token = auth.state.status === "signed_in" ? auth.state.token : null;
  const { context, partial, source } = resolveContext(me?.profile, prefs.context);
  const { state, retry } = useRequest(
    (signal) => api.discovery(context ? { grade: String(context.grade), track: context.stream } : {}, signal),
    [context?.grade, context?.stream],
  );
  const tracks = state.status === "success" ? state.data.tracks : undefined;

  async function choose(next: Partial<LearnContext>) {
    update({ context: next });
    setSaved(null);
    if (!next.grade || !next.stream) return;
    // The learner's own profile keeps the choice (existing profile service); a guest's choice stays on this device.
    if (token && me) {
      try {
        await api.saveProfile(token, profileWith(me, next as LearnContext));
        await auth.refresh();
        setSaved("profile");
      } catch (e) {
        auth.handleError(e);
        setSaved("device");
      }
    } else {
      setSaved("device");
    }
    setEditing(false);
  }

  const ready = loaded && auth.state.status !== "loading";
  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      <ScrollView contentContainerStyle={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.lg }}>
        <T variant="title" accessibilityRole="header">
          Learn
        </T>
        {!ready ? (
          <Loading label="Loading" />
        ) : !context || editing ? (
          <LearnContextPicker value={partial} tracks={tracks} onChange={choose} onCancel={context ? () => setEditing(false) : undefined} saving={saved} />
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm }}>
            <View style={{ flex: 1 }}>
              <T style={{ fontWeight: "700" }}>{contextLine(context)}</T>
              <T variant="small">{source === "profile" ? "From your profile" : token ? "Chosen on this device" : "Chosen on this device · sign in to keep it"}</T>
            </View>
            <LinkButton label="Change" accessibilityLabel="Change class or study group" onPress={() => setEditing(true)} />
          </View>
        )}
        {token ? <ContinueReading token={token} /> : null}
        {context && state.status === "loading" && <Loading label="Loading your subjects" />}
        {context && state.status === "error" && <ErrorState error={state.error} onRetry={retry} />}
        {context && state.status === "success" && <Books data={state.data} context={context} />}
        {token ? <LinkButton label="Your dashboard and tests" onPress={() => router.push("/dashboard")} /> : null}
      </ScrollView>
    </SafeAreaView>
  );
}

/** The saved profile with the new class and group; the group's subjects replace the subject list. */
function profileWith(me: Me, ctx: LearnContext): ProfileInput {
  const p = me.profile;
  const subjects = (STREAMS_SUBJECTS[ctx.stream] ?? []) as ProfileInput["subjects"];
  return {
    grade: ctx.grade,
    stream: ctx.stream,
    subjects,
    target_exams: p?.target_exams ?? [],
    target_year: p?.target_year ?? null,
    explanation_language: p?.explanation_language ?? "en",
    daily_minutes: p?.daily_minutes ?? null,
  };
}

const STREAMS_SUBJECTS: Record<string, string[]> = {
  pre_medical: ["biology", "chemistry", "physics"],
  pre_engineering: ["mathematics", "chemistry", "physics"],
  ics: ["computer_science", "mathematics", "physics"],
};

/** Only a real reading position (a published lesson this learner opened) becomes "Continue reading". */
function ContinueReading({ token }: { token: string }) {
  const req = useRequest((signal) => api.dashboard(token, signal), [token]);
  if (req.state.status !== "success") return null;
  const next = req.state.data.continue_learning;
  const unfinished = req.state.data.unfinished;
  return (
    <View style={{ gap: Space.sm }}>
      {next ? (
        <Card label={`Continue reading: ${next.title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: next.chapter_id } })}>
          <T variant="eyebrow">Continue reading</T>
          <T style={{ fontWeight: "600" }}>{next.title}</T>
          <T variant="small">
            {GRADE_LABEL[next.grade]} · Chapter {next.chapter_number}: {next.chapter_title}
          </T>
        </Card>
      ) : null}
      {unfinished.map((u) => (
        // P19.S1.T1 (JOURNEYS-01): pick up a test started on any device.
        <Card
          key={u.attempt_id}
          label={`Unfinished ${u.kind} test, ${GRADE_LABEL[u.grade]} ${u.subject.replace("_", " ")}: continue`}
          onPress={() =>
            u.kind === "written"
              ? router.push({ pathname: "/written/[id]", params: { id: u.attempt_id } })
              : router.push({ pathname: "/attempt/[id]", params: { id: u.attempt_id } })
          }>
          <T variant="eyebrow">Unfinished test</T>
          <T style={{ fontWeight: "600" }}>
            {u.kind.charAt(0).toUpperCase() + u.kind.slice(1)} · {GRADE_LABEL[u.grade]} {u.subject.replace("_", " ")}
          </T>
        </Card>
      ))}
    </View>
  );
}

function Books({ data, context }: { data: Discovery; context: LearnContext }) {
  const c = useTheme();
  const scheme = useScheme();
  const books = data.books.filter((book) => book.grade === context.grade);
  const track = data.tracks.find((t) => t.code === context.stream);
  const streamName = STREAMS.find(([code]) => code === context.stream)?.[1] ?? "";
  return (
    <View style={{ gap: Space.lg }}>
      <View style={{ gap: Space.sm }} accessibilityRole="list">
        <T variant="heading" accessibilityRole="header">
          Your subjects
        </T>
        {track?.note ? <T variant="small">{track.note}</T> : null}
        {data.ambiguous_editions.length > 0 && (
          <Notice tone="warn" title="More than one edition is effective today">
            {data.ambiguous_editions.map((item) => `${GRADE_LABEL[item.grade] ?? `Class ${item.grade}`} ${item.subject_name}`).join("; ")}. Those books are not
            shown, because the app does not choose an edition for you.
          </Notice>
        )}
        {books.length === 0 && data.ambiguous_editions.length === 0 ? (
          <Notice title={`No ${GRADE_LABEL[context.grade]} ${streamName} books yet`}>Choose another class or group, or check back later.</Notice>
        ) : null}
        {books.map((book) => {
          const key = subjectKey(book.subject);
          const accent = key ? SubjectAccents[key][scheme].accent : c.accent;
          return (
            <Card
              key={book.book_id}
              label={`${GRADE_LABEL[book.grade] ?? ""} ${book.subject_name}, ${book.chapter_count} ${book.chapter_label.toLowerCase()}s`}
              style={{ borderLeftWidth: 4, borderLeftColor: accent }}
              onPress={() => router.push({ pathname: "/book/[grade]/[subject]", params: { grade: String(book.grade), subject: book.subject } })}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: Space.sm }}>
                <T variant="subheading" style={{ flexShrink: 1 }}>
                  {book.subject_name}
                </T>
                {book.completeness !== "complete" && <Badge tone="warn">Source has gaps</Badge>}
              </View>
              <T variant="small">
                {book.chapter_count} {book.chapter_label.toLowerCase()}s · {bookSummary(book)}
              </T>
            </Card>
          );
        })}
      </View>
      {data.previews.filter((p) => p.grade === context.grade).length > 0 && (
        <View style={{ gap: Space.sm }}>
          <T variant="heading" accessibilityRole="header">
            Free preview lessons
          </T>
          {data.previews
            .filter((p) => p.grade === context.grade)
            .map((preview) => (
              <Card key={preview.lesson_id} label={preview.title} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: preview.chapter_id } })}>
                <T style={{ fontWeight: "600" }}>{preview.title}</T>
                <T variant="small">
                  {GRADE_LABEL[preview.grade]} {preview.subject_name} · Chapter {preview.chapter_number}
                </T>
              </Card>
            ))}
        </View>
      )}
      <T variant="small">{data.plans_note}</T>
    </View>
  );
}
