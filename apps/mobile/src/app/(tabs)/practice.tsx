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
  const [kind, setKind] = useState<"mcq" | "written">("mcq");
  const availability = useRequest((signal) => api.practiceAvailability(token, grade, subject, signal), [token, grade, subject]);
  const [chapters, setChapters] = useState<string[]>([]);
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
    try {
      const form = await api.createPracticeForm(token, key.current, {
        grade,
        subject,
        chapter_ids: chapters,
        question_count: Number(count) || 1,
        timed_minutes: timed ? Number(minutes) || 15 : null,
        feedback_mode: immediate ? "immediate" : "deferred",
      });
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
      <Choices label="Class" options={[[11, GRADE_LABEL[11]], [12, GRADE_LABEL[12]]] as const} selected={[grade]} onToggle={(g) => { setGrade(g); setChapters([]); }} />
      <Choices label="Subject" options={SUBJECTS} selected={[subject]} onToggle={(s) => { setSubject(s); setChapters([]); }} />
      <Choices
        label="Kind of test"
        options={[["mcq", "Multiple choice"], ["written", "Written answers"]] as const}
        selected={[kind]}
        onToggle={setKind}
      />
      {kind === "written" ? <WrittenBuilder token={token} grade={grade} subject={subject} /> : mcqBody()}
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
                  onPress={() => setChapters(on ? chapters.filter((x) => x !== ch.chapter_id) : [...chapters, ch.chapter_id])}
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
                  <T variant="small">{disabled ? "none yet" : `${ch.questions} questions`}</T>
                </Pressable>
              );
            })}
          </View>
          <Field label="Questions" value={count} onChangeText={setCount} keyboardType="number-pad" maxLength={3} />
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
          <FormError message={error} />
          <Button label="Start test" onPress={start} busy={busy} disabled={chapters.length === 0} />
        </View>
      )}
      </View>
    );
  }
}
