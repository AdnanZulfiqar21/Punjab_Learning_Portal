// Written practice builder (W04.S1) on native: only reviewed questions with a published rubric, only where a funded
// teacher reviewer exists and marking isn't at capacity. Starting reserves allowance on the server.
import { router } from "expo-router";
import { useRef, useState } from "react";
import { Pressable, Switch, View } from "react-native";

import { Button, Choices, Field, FormError } from "@/components/form";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";

const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;

export function WrittenBuilder({ token, grade, subject }: { token: string; grade: number; subject: string }) {
  const c = useTheme();
  const availability = useRequest((signal) => api.writtenAvailability(token, grade, subject, signal), [token, grade, subject]);
  const [chapters, setChapters] = useState<string[]>([]);
  const [count, setCount] = useState("1");
  const [type, setType] = useState<"short" | "long" | "mixed">("mixed");
  const [timed, setTimed] = useState(false);
  const [minutes, setMinutes] = useState("30");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null); // one idempotency key per request; a fresh one after an error

  async function start() {
    setError(null);
    setBusy(true);
    key.current ??= newKey();
    try {
      const form = await api.createWrittenForm(token, key.current, {
        grade,
        subject,
        chapter_ids: chapters,
        question_type: type,
        question_count: Number(count) || 1,
        writing_minutes: timed ? Number(minutes) || 30 : null,
      });
      const attempt = await api.startWritten(token, form.id);
      key.current = null;
      router.push({ pathname: "/written/[id]", params: { id: attempt.id } });
    } catch (e) {
      key.current = null;
      setError(e instanceof ApiError ? e.message : "Could not start the written test.");
    } finally {
      setBusy(false);
    }
  }

  if (availability.state.status === "loading") return <Loading label="Loading chapters" />;
  if (availability.state.status === "error") return <ErrorState error={availability.state.error} onRetry={availability.retry} />;
  const a = availability.state.data;
  if (!a.review_staffed) {
    return <Notice title="Not offered yet">No teacher reviewer is available to mark written answers in this subject yet.</Notice>;
  }
  if (a.chapters.every((ch) => ch.questions === 0)) {
    return <Notice title="No approved written questions yet">Questions appear once a subject reviewer approves them with a marking rubric.</Notice>;
  }
  return (
    <View style={{ gap: Space.lg }}>
      {!a.review_accepting && (
        <Notice tone="warn" title="Marking is full right now">
          Teacher marking for this subject is at capacity, so new written tests can&apos;t start. Try again later.
        </Notice>
      )}
      <View style={{ gap: Space.xs }}>
        <T style={{ fontWeight: "600" }}>Chapters</T>
        {a.chapters.map((ch) => {
          const on = chapters.includes(ch.chapter_id);
          const disabled = ch.questions === 0;
          return (
            <Pressable
              key={ch.chapter_id}
              accessibilityRole="checkbox"
              accessibilityLabel={`Chapter ${ch.number}: ${ch.title}`}
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
              <T variant="small">{disabled ? "none yet" : `${ch.questions} written`}</T>
            </Pressable>
          );
        })}
      </View>
      <Choices
        label="Question type"
        options={[["mixed", "Mixed"], ["short", "Short"], ["long", "Long"]] as const}
        selected={[type]}
        onToggle={setType}
      />
      <Field label="Written questions" value={count} onChangeText={setCount} keyboardType="number-pad" maxLength={2} />
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <T>Timed writing</T>
        <Switch value={timed} onValueChange={setTimed} accessibilityLabel="Timed writing" />
      </View>
      {timed && <Field label="Writing minutes" value={minutes} onChangeText={setMinutes} keyboardType="number-pad" maxLength={3} />}
      <T variant="small">
        Write on paper, then photograph each page here.
        {timed ? ` After the writing time you have ${Math.round(a.upload_allowance_s / 60)} minutes to upload.` : " The test shows when uploads close."} Nothing is
        marked until you submit.
      </T>
      <FormError message={error} />
      <Button label="Start written test" onPress={start} busy={busy} disabled={chapters.length === 0 || !a.review_accepting} />
    </View>
  );
}
