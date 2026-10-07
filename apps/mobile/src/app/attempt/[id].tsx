// Native attempt runner (P10.S2): selected → pending → saved only after the server's receipt (§10.5). Unacknowledged
// operations live in an app-private file, are re-sent on return, and are flushed when the app goes to the background.
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, Pressable, ScrollView, View } from "react-native";
import type { AnswerOpResult, PracticeAttempt, RevealResult } from "@portal/contracts";

import { Button } from "@/components/form";
import { LessonBlocks } from "@/components/lesson-blocks";
import { ErrorState, Loading, Notice, T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { readQueue, writeQueue, type QueuedOp } from "@/lib/op-store";

const DEBOUNCE_MS = 400;
const PRE_FLUSH_MS = 5000;
type ItemState = { option: string | null; status: "saved" | "pending" | "rejected" | "empty"; reason?: string; revision: number };
const REASON: Record<string, string> = {
  stale: "A newer answer from another device is already saved.",
  invalid: "This answer couldn't be accepted.",
  late: "It reached the server after the time limit, so it wasn't counted.",
  finalised: "The test had already been submitted.",
  locked: "This question was checked and can't be changed.",
  conflict: "This change clashed with an earlier one.",
};
const uuid = () =>
  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });

export default function AttemptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { state } = useAuth();
  // Wait for the stored session to load before requesting anything; never treat "not loaded yet" as signed out.
  if (state.status === "loading") return <Loading label="Checking your sign-in" />;
  if (state.status !== "signed_in") return <Notice title="Sign in to continue">Open the Account tab to sign in.</Notice>;
  return <AttemptLoader id={id} token={state.token} />;
}

function AttemptLoader({ id, token }: { id: string; token: string }) {
  const { handleError } = useAuth();
  const req = useRequest((signal) => api.attempt(token, id, signal), [token, id]);
  useEffect(() => {
    if (req.state.status === "error") handleError(req.state.error); // a real 401 ends the session
  }, [req.state, handleError]);
  if (req.state.status === "loading") return <Loading label="Loading your test" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const attempt = req.state.data;
  if (attempt.status !== "active") return <Submitted attempt={attempt} />;
  return <Runner key={attempt.id} attempt={attempt} token={token} onFinalised={req.retry} />;
}

function Submitted({ attempt }: { attempt: PracticeAttempt }) {
  const c = useTheme();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: "Test submitted" }} />
      <Notice title={attempt.receipt?.reason === "expiry" ? "Time is up" : "Submitted"}>
        {attempt.receipt
          ? `${attempt.receipt.answered_count} of ${attempt.receipt.question_count} answered · receipt ${attempt.receipt.id.slice(0, 8)}`
          : "Your answers are saved."}
      </Notice>
      <Button label="See your result" onPress={() => router.replace({ pathname: "/result/[id]", params: { id: attempt.id } })} />
    </ScrollView>
  );
}

function Runner({ attempt, token, onFinalised }: { attempt: PracticeAttempt; token: string; onFinalised: () => void }) {
  const c = useTheme();
  const total = attempt.items.length;
  const [current, setCurrent] = useState(1);
  const [items, setItems] = useState<Record<number, ItemState>>(() => {
    const out: Record<number, ItemState> = {};
    for (const it of attempt.items) out[it.position] = { option: null, status: "empty", revision: 0 };
    for (const a of attempt.answers) out[a.position] = { option: a.option_id, status: a.option_id ? "saved" : "empty", revision: a.revision };
    return out;
  });
  const [locked, setLocked] = useState<Set<number>>(() => new Set(attempt.answers.filter((a) => a.revealed).map((a) => a.position)));
  const [revealed, setRevealed] = useState<Record<number, RevealResult>>({});
  const [connection, setConnection] = useState<"ok" | "retrying">("ok");
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [now, setNow] = useState<number | null>(null);
  const queue = useRef<QueuedOp[]>([]);
  const submitKey = useRef<string | undefined>(undefined);
  const inflight = useRef<Promise<void> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelay = useRef(2000);
  const offset = useRef<number | null>(null);
  const flushRef = useRef<() => Promise<void>>(() => Promise.resolve());
  const deadline = attempt.deadline_at ? new Date(attempt.deadline_at).getTime() : null;
  const cutoff = attempt.cutoff_at ? new Date(attempt.cutoff_at).getTime() : null;
  const closed = deadline !== null && now !== null && now >= deadline;

  const persist = useCallback(() => writeQueue(attempt.id, { ops: queue.current, submitKey: submitKey.current }), [attempt.id]);

  const apply = useCallback((results: AnswerOpResult[]) => {
    const done = new Set(results.map((r) => r.op_id));
    queue.current = queue.current.filter((o) => !done.has(o.op_id));
    setItems((prev) => {
      const next = { ...prev };
      for (const r of results) {
        if (queue.current.some((o) => o.position === r.position)) continue; // a newer local change is on its way
        const cur = next[r.position];
        if (r.disposition === "accepted") next[r.position] = { option: r.option_id ?? null, status: r.option_id ? "saved" : "empty", revision: r.revision };
        else if (cur && cur.revision <= r.revision) next[r.position] = { ...cur, status: "rejected", reason: REASON[r.disposition] ?? "Not saved." };
      }
      return next;
    });
    setLocked((prev) => {
      const next = new Set(prev);
      for (const r of results) if (r.disposition === "locked") next.add(r.position);
      return next;
    });
  }, []);

  const flush = useCallback(async (): Promise<void> => {
    if (inflight.current) return inflight.current;
    if (queue.current.length === 0) return;
    const batch = queue.current.slice(0, 50);
    inflight.current = (async () => {
      try {
        const out = await api.saveAnswers(token, attempt.id, batch);
        retryDelay.current = 2000;
        setConnection("ok");
        apply(out.results);
        await persist();
        if (out.status !== "active") onFinalised();
      } catch (e) {
        if (e instanceof ApiError && e.kind === "conflict") {
          const results = ((e.problem as { results?: AnswerOpResult[] } | null | undefined)?.results ?? []) as AnswerOpResult[];
          apply(results);
          await persist();
          onFinalised();
          return;
        }
        setConnection("retrying");
        const delay = retryDelay.current;
        retryDelay.current = Math.min(15_000, delay * 2);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => void flushRef.current(), delay + Math.random() * 500);
      }
    })();
    try {
      await inflight.current;
    } finally {
      inflight.current = null;
    }
    if (queue.current.length > 0 && retryDelay.current === 2000) void flushRef.current();
  }, [apply, attempt.id, onFinalised, persist, token]);

  useEffect(() => {
    flushRef.current = flush;
  }, [flush]);

  // Restore unacknowledged work saved on this device, then re-send it.
  useEffect(() => {
    let cancelled = false;
    void readQueue(attempt.id).then((stored) => {
      if (cancelled) return;
      submitKey.current = stored.submitKey;
      if (stored.ops.length === 0) return;
      queue.current = stored.ops;
      setItems((prev) => {
        const next = { ...prev };
        for (const o of stored.ops) {
          const cur = next[o.position];
          if (!cur || o.revision >= cur.revision) next[o.position] = { option: o.option_id, status: "pending", revision: o.revision };
        }
        return next;
      });
      void flushRef.current();
    });
    const sub = AppState.addEventListener("change", (s) => {
      if (s !== "active") void flushRef.current(); // flush before the app is suspended
      else void flushRef.current();
    });
    return () => {
      cancelled = true;
      sub.remove();
    };
  }, [attempt.id]);

  // Display clock (server offset measured on the first tick), pre-flush at D − 5 s, flush at D, refresh after C.
  useEffect(() => {
    if (deadline === null) return;
    let preFlushed = false;
    const t = setInterval(() => {
      offset.current ??= new Date(attempt.server_now).getTime() - Date.now();
      const n = Date.now() + offset.current;
      setNow(n);
      if (!preFlushed && n >= deadline - PRE_FLUSH_MS) {
        preFlushed = true;
        void flushRef.current();
      }
      if (n >= deadline) void flushRef.current();
      if (cutoff !== null && n > cutoff + 1500) {
        clearInterval(t);
        void flushRef.current().then(onFinalised);
      }
    }, 500);
    return () => clearInterval(t);
  }, [attempt.server_now, cutoff, deadline, onFinalised]);

  function choose(position: number, option: string | null) {
    if (closed || submitting || locked.has(position)) return;
    const cur = items[position];
    const pendingMax = Math.max(0, ...queue.current.filter((o) => o.position === position).map((o) => o.revision));
    const revision = Math.max(cur?.revision ?? 0, pendingMax) + 1;
    queue.current = [...queue.current, { op_id: uuid(), position, revision, option_id: option }];
    void persist();
    setItems((prev) => ({ ...prev, [position]: { option, status: "pending", revision } }));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flushRef.current(), DEBOUNCE_MS);
  }

  async function check(position: number) {
    await flush();
    try {
      const res = await api.reveal(token, attempt.id, position);
      setRevealed((r) => ({ ...r, [position]: res }));
      setLocked((l) => new Set(l).add(position));
    } catch {
      /* the answer stays as it is; the learner can try again */
    }
  }

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    if (timer.current) clearTimeout(timer.current);
    if (inflight.current) await inflight.current;
    submitKey.current ??= uuid().replaceAll("-", "");
    await persist(); // retries reuse the same submission key
    try {
      await api.submitAttempt(token, attempt.id, submitKey.current, queue.current);
      queue.current = [];
      submitKey.current = undefined;
      await writeQueue(attempt.id, { ops: [] });
      router.replace({ pathname: "/result/[id]", params: { id: attempt.id } });
    } catch (e) {
      setSubmitting(false);
      setSubmitError(e instanceof ApiError ? e.message : "Couldn't submit. Nothing was lost; try again.");
    }
  }

  const answered = Object.values(items).filter((i) => i.option !== null).length;
  const pending = Object.values(items).filter((i) => i.status === "pending").length;
  const item = attempt.items.find((i) => i.position === current)!;
  const state = items[current];
  const remaining = deadline !== null && now !== null ? Math.max(0, deadline - now) : null;
  const disabled = closed || submitting || locked.has(current);

  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }}>
      <Stack.Screen options={{ title: `Question ${current} of ${total}` }} />
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <T variant="small" accessibilityLiveRegion="polite" style={{ color: connection === "retrying" ? c.warn : c.muted, flex: 1 }}>
          {connection === "retrying" ? "Offline: answers are kept on this device and will be sent again" : pending > 0 ? `Saving ${pending}…` : `${answered} answered · all saved`}
        </T>
        {deadline !== null && (
          <T accessibilityLabel="Time remaining" style={{ fontVariant: ["tabular-nums"], color: remaining !== null && remaining < 60_000 ? c.danger : c.text }}>
            {remaining === null ? "--:--" : closed ? "Time is up" : `${Math.floor(remaining / 60_000)}:${String(Math.floor((remaining % 60_000) / 1000)).padStart(2, "0")}`}
          </T>
        )}
      </View>

      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.xs }} accessibilityLabel="Questions">
        {attempt.items.map((it) => {
          const st = items[it.position];
          const bg = st.status === "saved" ? c.accentSoft : st.status === "pending" ? c.warnSoft : st.status === "rejected" ? c.dangerSoft : c.surface;
          return (
            <Pressable
              key={it.position}
              accessibilityRole="button"
              accessibilityLabel={`Question ${it.position}: ${st.status === "empty" ? "not answered" : st.status}`}
              onPress={() => setCurrent(it.position)}
              style={{ width: 40, height: 40, borderRadius: Radius.sm, borderWidth: it.position === current ? 2 : 1, borderColor: it.position === current ? c.accent : c.border, backgroundColor: bg, alignItems: "center", justifyContent: "center" }}>
              <T variant="small">{it.position}</T>
            </Pressable>
          );
        })}
      </View>

      <View style={{ gap: Space.md, padding: Space.lg, borderRadius: Radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface }}>
        <LessonBlocks blocks={item.stem as { type: string }[]} />
        <View accessibilityRole="radiogroup" style={{ gap: Space.sm }}>
          {item.options.map((o, idx) => {
            const reveal = revealed[current];
            const selected = state.option === o.id;
            const border = reveal ? (o.id === reveal.correct_option_id ? c.accent : o.id === reveal.chosen ? c.danger : c.border) : selected ? c.accent : c.border;
            return (
              <Pressable
                key={o.id}
                accessibilityRole="radio"
                aria-checked={selected}
                aria-disabled={disabled}
                disabled={disabled}
                onPress={() => choose(current, o.id)}
                style={{ flexDirection: "row", gap: Space.sm, padding: Space.md, borderRadius: Radius.sm, borderWidth: selected ? 2 : 1, borderColor: border, backgroundColor: selected ? c.accentSoft : c.surface, opacity: disabled && !selected ? 0.7 : 1 }}>
                <T style={{ fontWeight: "600", width: 20 }}>{String.fromCharCode(65 + idx)}</T>
                <View style={{ flex: 1 }}>
                  <LessonBlocks blocks={o.blocks as { type: string }[]} />
                </View>
              </Pressable>
            );
          })}
        </View>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.md, alignItems: "center" }}>
          {state.option !== null && !disabled && <Button variant="link" label="Clear answer" onPress={() => choose(current, null)} />}
          {attempt.feedback_mode === "immediate" && state.status === "saved" && state.option !== null && !revealed[current] && !locked.has(current) && (
            <Button variant="secondary" label="Check answer" onPress={() => void check(current)} />
          )}
          <T variant="small" style={{ color: state.status === "rejected" ? c.danger : c.muted }}>
            {state.status === "saved" ? "Saved" : state.status === "pending" ? "Saving…" : state.status === "rejected" ? `Not saved: ${state.reason}` : ""}
          </T>
        </View>
        {revealed[current] && (
          <View accessibilityLiveRegion="polite" style={{ gap: Space.xs, padding: Space.md, borderRadius: Radius.sm, backgroundColor: c.surfaceMuted }}>
            <T style={{ fontWeight: "600" }}>{revealed[current].correct ? "Correct" : "Not quite"}</T>
            <LessonBlocks blocks={((revealed[current].explanation as { correct?: unknown[] }).correct ?? []) as { type: string }[]} />
          </View>
        )}
      </View>

      <View style={{ flexDirection: "row", gap: Space.sm }}>
        <View style={{ flex: 1 }}>
          <Button variant="secondary" label="← Previous" onPress={() => setCurrent(Math.max(1, current - 1))} disabled={current === 1} />
        </View>
        <View style={{ flex: 1 }}>
          <Button variant="secondary" label="Next →" onPress={() => setCurrent(Math.min(total, current + 1))} disabled={current === total} />
        </View>
      </View>
      {!confirming ? (
        <Button label="Finish test" onPress={() => setConfirming(true)} disabled={submitting} />
      ) : (
        <View style={{ gap: Space.sm, padding: Space.lg, borderRadius: Radius.md, borderWidth: 1, borderColor: c.accent, backgroundColor: c.surface }}>
          <T variant="heading">Submit your test?</T>
          <T>
            {answered} answered · {total - answered} not answered{pending > 0 ? ` · ${pending} still being saved (sent with your submission)` : ""}
          </T>
          <T variant="small">After you submit you can’t change any answer.</T>
          {submitError ? <T style={{ color: c.danger }}>{submitError}</T> : null}
          <Button label={submitError ? "Try again" : "Submit"} onPress={() => void submit()} busy={submitting} />
          <Button variant="link" label="Keep working" onPress={() => setConfirming(false)} disabled={submitting} />
        </View>
      )}
    </ScrollView>
  );
}
