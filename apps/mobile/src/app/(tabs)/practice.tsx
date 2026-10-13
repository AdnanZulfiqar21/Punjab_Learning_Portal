import { router } from "expo-router";
import { useRef, useState } from "react";
import { Pressable, ScrollView, Switch, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button, Choices, Field, FormError } from "@/components/form";
import { PlanCard } from "@/components/plan-card";
import { WrittenBuilder } from "@/components/written-builder";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Radius, Space, TAB_SCREEN_TOP } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError, GRADE_LABEL, SUBJECTS, type SubjectCode } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;

export default function PracticeScreen() {
  const c = useTheme();
  const { state } = useAuth();
  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: Space.lg, paddingTop: TAB_SCREEN_TOP, gap: Space.lg }}>
        <T variant="title">Practice</T>
        <T variant="muted">Build a test from your textbook chapters. Only questions approved by an independent subject reviewer are used.</T>
        {state.status === "signed_in" && (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.sm }}>
            <Button variant="link" label="Mock tests" onPress={() => router.push("/mocks")} />
            <Button variant="link" label="Mistake notebook" onPress={() => router.push("/notebook")} />
            <Button variant="link" label="Progress" onPress={() => router.push("/progress")} />
            <Button variant="link" label="What you've shown" onPress={() => router.push("/evidence")} />
            <Button variant="link" label="Study plan" onPress={() => router.push("/plan")} />
          </View>
        )}
        {state.status === "loading" && <Loading label="Checking your sign-in" />}
        {(state.status === "signed_out" || state.status === "unavailable") && (
          <View style={{ gap: Space.md }}>
            <Notice title="Sign in to practise">Your answers and results are saved to your account.</Notice>
            <Button label="Go to Account" onPress={() => router.navigate("/account")} />
          </View>
        )}
        {state.status === "signed_in" && (
          <Gate
            token={state.token}
            initialGrade={(state.me.profile?.grade as 11 | 12 | undefined) ?? 11}
            initialSubject={(state.me.profile?.subjects?.[0] as SubjectCode | undefined) ?? "biology"}
          />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

/** New practice needs a plan (P14): show the plan, and the builder only when access is active. */
function Gate({ token, initialGrade, initialSubject }: { token: string; initialGrade: 11 | 12; initialSubject: SubjectCode }) {
  const access = useRequest((signal) => api.access(token, signal), [token]);
  if (access.state.status === "loading") return <Loading label="Checking your plan" />;
  if (access.state.status === "error") return <ErrorState error={access.state.error} onRetry={access.retry} />;
  return (
    <View style={{ gap: Space.lg }}>
      <PlanCard access={access.state.data} token={token} onChange={() => access.retry()} purpose="Practice tests" />
      {access.state.data.has_access && <Builder token={token} initialGrade={initialGrade} initialSubject={initialSubject} />}
    </View>
  );
}

function Builder({ token, initialGrade, initialSubject }: { token: string; initialGrade: 11 | 12; initialSubject: SubjectCode }) {
  const c = useTheme();
  const [grade, setGrade] = useState<11 | 12>(initialGrade);
  const [subject, setSubject] = useState<SubjectCode>(initialSubject);
  const [kind, setKind] = useState<"mcq" | "written" | "mix">("mcq");
  // P09.S1.T3: custom practice from several subjects of this class, each with its own count (blank = left out).
  const [mix, setMix] = useState<Partial<Record<SubjectCode, string>>>({});
  const availability = useRequest((signal) => api.practiceAvailability(token, grade, subject, signal), [token, grade, subject]);
  const [chapters, setChapters] = useState<string[]>([]);
  // P11.S3.T1 (PRACTICE-CONFIG-01): optional topics inside the chosen chapters; any chosen limits the test to them.
  const [topics, setTopics] = useState<string[]>([]);
  // P09.S1.T2 (SCOPES-01): halves follow the book's chapter order; "combined" is this subject's XI and XII books.
  const [cover, setCover] = useState<"chapters" | "half_1" | "half_2" | "full_book" | "combined">("chapters");
  const [count, setCount] = useState("10");
  const [immediate, setImmediate] = useState(false);
  const [timed, setTimed] = useState(false);
  const [minutes, setMinutes] = useState("15");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null); // one idempotency key per request; a new one after an error

  async function start() {
    setError(null);
    setBusy(true);
    key.current ??= newKey();
    const shares = SUBJECTS.map(([code]) => ({ subject: code, questions: Number(mix[code]) || 0 })).filter((m) => m.questions > 0);
    if (kind === "mix" && shares.length < 2) {
      setError("Choose at least two subjects for a custom mix.");
      setBusy(false);
      return;
    }
    try {
      const timing = { timed_minutes: timed ? Number(minutes) || 15 : null, feedback_mode: immediate ? "immediate" : "deferred" };
      const form = await api.createPracticeForm(
        token,
        key.current,
        kind === "mix"
          ? {
              grade,
              subject: shares[0].subject,
              scope: "multi_subject",
              mix: shares,
              question_count: shares.reduce((n, m) => n + m.questions, 0),
              ...timing,
            }
          : {
              grade,
              subject,
              scope: cover.startsWith("half") ? "half_book" : cover,
              half: cover === "half_1" ? 1 : cover === "half_2" ? 2 : null,
              chapter_ids: cover === "chapters" ? chapters : [],
              topic_ids: cover === "chapters" ? topics : [],
              question_count: Number(count) || 1,
              ...timing,
            },
      );
      const attempt = await api.startAttempt(token, form.id);
      key.current = null;
      router.push({ pathname: "/attempt/[id]", params: { id: attempt.id } });
    } catch (e) {
      key.current = null;
      const p = e instanceof ApiError ? (e.problem as { available?: number } | null | undefined) : null;
      setError(
        e instanceof ApiError
          ? `${e.message}${p?.available !== undefined ? ` You can ask for up to ${p.available}.` : ""}`
          : "Could not start the test.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: Space.lg }}>
      <Choices label="Class" options={[[11, GRADE_LABEL[11]], [12, GRADE_LABEL[12]]] as const} selected={[grade]} onToggle={(g) => { setGrade(g); setChapters([]); setTopics([]); }} />
      <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={(s) => { setSubject(s); setChapters([]); setTopics([]); }} />
      <Choices
        label="Kind of test"
        options={[["mcq", "Multiple choice"], ["mix", "Several subjects"], ["written", "Written answers"]] as const}
        selected={[kind]}
        onToggle={setKind}
      />
      {kind === "written" ? <WrittenBuilder token={token} grade={grade} subject={subject} /> : kind === "mix" ? mixBody() : mcqBody()}
    </View>
  );

  // A render function (not a component), so text fields keep focus across renders.
  function mcqBody() {
    return (
      <View style={{ gap: Space.lg }}>
      {availability.state.status === "loading" && <Loading label="Loading chapters" />}
      {availability.state.status === "error" && <ErrorState error={availability.state.error} onRetry={availability.retry} />}
      {availability.state.status === "success" && availability.state.data.chapters.every((ch) => ch.questions === 0) && (
        <Notice title="No approved practice questions yet">
          Questions appear here once a subject reviewer approves them and they are published. Nothing unreviewed is ever used.
        </Notice>
      )}
      {availability.state.status === "success" && availability.state.data.chapters.some((ch) => ch.questions > 0) && (
        <View style={{ gap: Space.lg }}>
          <Choices
            label="What to cover"
            options={
              [
                ["chapters", "Chosen chapters"],
                ["half_1", "First half"],
                ["half_2", "Second half"],
                ["full_book", "Whole book"],
                ["combined", "XI and XII together"],
              ] as const
            }
            selected={[cover]}
            onToggle={setCover}
          />
          {cover === "chapters" && (
          <View style={{ gap: Space.xs }}>
            <T style={{ fontWeight: "600" }}>Chapters</T>
            {availability.state.data.chapters.map((ch) => {
              const on = chapters.includes(ch.chapter_id);
              const disabled = ch.questions === 0;
              return (
                <Pressable
                  key={ch.chapter_id}
                  accessibilityRole="checkbox"
                  aria-checked={on}
                  aria-disabled={disabled}
                  disabled={disabled}
                  onPress={() => {
                    setChapters(on ? chapters.filter((x) => x !== ch.chapter_id) : [...chapters, ch.chapter_id]);
                    if (on) setTopics((ts) => ts.filter((t) => !(ch.topics ?? []).some((x) => x.topic_id === t)));
                  }}
                  style={{
                    flexDirection: "row",
                    gap: Space.sm,
                    alignItems: "center",
                    padding: Space.md,
                    borderWidth: 1,
                    borderRadius: Radius.sm,
                    borderColor: on ? c.accent : c.border,
                    backgroundColor: on ? c.accentSoft : c.surface,
                    opacity: disabled ? 0.5 : 1,
                  }}>
                  <T style={{ flex: 1 }}>
                    Chapter {ch.number}: {ch.title}
                  </T>
                  <T variant="small">{disabled ? "none yet" : `${ch.questions} question${ch.questions === 1 ? "" : "s"}`}</T>
                </Pressable>
              );
            })}
            {availability.state.data.chapters
              .filter((ch) => chapters.includes(ch.chapter_id) && (ch.topics ?? []).length > 0)
              .map((ch) => (
                <View key={`topics-${ch.chapter_id}`} style={{ gap: Space.xs, paddingLeft: Space.lg }}>
                  <T variant="small">Chapter {ch.number}: only some topics? (optional; choosing any limits the whole test to them)</T>
                  {(ch.topics ?? []).map((t) => {
                    const picked = topics.includes(t.topic_id);
                    return (
                      <Pressable
                        key={t.topic_id}
                        accessibilityRole="checkbox"
                        aria-checked={picked}
                        onPress={() => setTopics(picked ? topics.filter((x) => x !== t.topic_id) : [...topics, t.topic_id])}
                        style={{
                          flexDirection: "row",
                          gap: Space.sm,
                          padding: Space.sm,
                          borderWidth: 1,
                          borderRadius: Radius.sm,
                          borderColor: picked ? c.accent : c.border,
                          backgroundColor: picked ? c.accentSoft : c.surface,
                        }}>
                        <T style={{ flex: 1 }}>
                          {t.number ? `${t.number} ` : ""}
                          {t.title}
                        </T>
                        <T variant="small">
                          {t.questions} question{t.questions === 1 ? "" : "s"}
                        </T>
                      </Pressable>
                    );
                  })}
                </View>
              ))}
          </View>
          )}
          <Field label="Questions" value={count} onChangeText={setCount} keyboardType="number-pad" maxLength={3} />
          {/* PRACTICE-CONFIG-01: a measured median, never a guess. */}
          <T variant="small">
            {availability.state.data.seconds_per_question
              ? `About ${Math.max(1, Math.ceil(((Number(count) || 1) * availability.state.data.seconds_per_question) / 60))} minutes for ${Number(count) || 1} questions, measured from ${availability.state.data.estimate_based_on} submitted tests here.`
              : "No time estimate yet: not enough submitted tests in this subject to measure one."}
          </T>
          {settings()}
          <FormError message={error} />
          <Button label="Start test" onPress={start} busy={busy} disabled={cover === "chapters" && chapters.length === 0} />
        </View>
      )}
      </View>
    );
  }

  function mixBody() {
    const total = SUBJECTS.reduce((n, [code]) => n + (Number(mix[code]) || 0), 0);
    return (
      <View style={{ gap: Space.lg }}>
        <T variant="small">
          Custom practice from each subject&apos;s whole book in {GRADE_LABEL[grade]}. It isn&apos;t an official test pattern; for those, use
          Mock tests. Choose two to five subjects.
        </T>
        {SUBJECTS.map(([code, name]) => (
          <Field
            key={code}
            label={`${name} questions`}
            value={mix[code] ?? ""}
            onChangeText={(v) => setMix({ ...mix, [code]: v })}
            keyboardType="number-pad"
            maxLength={3}
          />
        ))}
        <T variant="small" accessibilityLiveRegion="polite">
          {total} questions{total > 100 ? " (at most 100 in one test)" : ""}
        </T>
        {settings()}
        <FormError message={error} />
        <Button label="Start test" onPress={start} busy={busy} disabled={total === 0 || total > 100} />
      </View>
    );
  }

  // Feedback and timing, shared by the chapter test and the custom mix.
  function settings() {
    return (
      <View style={{ gap: Space.lg }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <T>Show feedback after each question</T>
            <Switch value={immediate} onValueChange={setImmediate} accessibilityLabel="Show feedback after each question" />
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <T>Timed</T>
            <Switch value={timed} onValueChange={setTimed} accessibilityLabel="Timed" />
          </View>
          {timed && (
            <View style={{ gap: Space.xs }}>
              <Field label="Minutes" value={minutes} onChangeText={setMinutes} keyboardType="number-pad" maxLength={3} />
              <T variant="small">
                Editing closes at the deadline. Answers that haven’t reached the server within 3 seconds after it can be rejected, so keep
                your connection steady near the end.
              </T>
            </View>
          )}
      </View>
    );
  }
}
