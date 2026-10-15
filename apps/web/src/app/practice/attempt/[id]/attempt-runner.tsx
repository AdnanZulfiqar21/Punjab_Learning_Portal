"use client";

// Attempt runner (P10.S2): selected → saving → saved only after the server's commit receipt (§10.5), or pending when
// a send failed or the change came from an earlier session; the five states are in lib/answer-state (ANSWER-STATES-01).
// Pending operations are kept in browser storage, so a refresh, a closed tab or a dropped connection never loses a
// selection that wasn't acknowledged; on return they are re-sent (exact replays get their original receipts).
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { AnswerOpResult, PracticeAttempt, RevealResult } from "@portal/contracts";
import { continueHere, revealItem, saveAnswers, setFlags, submitAttempt, type Op } from "@/app/actions/practice";
import { LessonBlocks } from "@/components/lesson-blocks";
import { HelpLink } from "@/components/help-link";
import { answerState, PALETTE_LABEL, stateLine, type AnswerState, type ItemStatus } from "@/lib/answer-state";

const DEBOUNCE_MS = 400; // ≤ 500 ms (P10.S2.T1)
const PRE_FLUSH_MS = 5000; // best-effort flush at D − 5 s
type Stored = { ops: Op[]; submitKey?: string };
type ItemState = { option: string | null; status: ItemStatus; reason?: string; revision: number; restored?: boolean };
const TONE: Record<AnswerState, string> = {
  empty: "border-border bg-surface",
  selected: "border-accent bg-accent-soft",
  saving: "border-warn bg-warn-soft",
  pending: "border-dashed border-warn bg-warn-soft",
  saved: "border-ok bg-ok-soft",
  rejected: "border-danger bg-danger-soft",
};

const OFFLINE = "Can't reach the service. Your answers are kept on this device and will be sent again.";
/** A server action whose request never reached the server (offline, dropped) rejects instead of returning; treat that
 *  like any other failure so the runner retries, and nothing waits on a promise that already failed (ANSWER-STATES-01). */
async function reach<T>(call: () => Promise<T>, failed: T): Promise<T> {
  try {
    return await call();
  } catch {
    return failed;
  }
}

const storageKey = (id: string) => `practice-queue:${id}`;
function readRaw(id: string): string | null {
  try {
    return window.localStorage.getItem(storageKey(id));
  } catch {
    return null;
  }
}
function parseStored(raw: string | null): Stored {
  try {
    const parsed = JSON.parse(raw ?? "") as Stored;
    return { ops: Array.isArray(parsed.ops) ? parsed.ops : [], submitKey: parsed.submitKey };
  } catch {
    return { ops: [] };
  }
}
const readStored = (id: string) => parseStored(readRaw(id));
function writeStored(id: string, value: Stored) {
  try {
    if (value.ops.length === 0 && !value.submitKey) window.localStorage.removeItem(storageKey(id));
    else window.localStorage.setItem(storageKey(id), JSON.stringify(value));
  } catch {
    /* storage unavailable: answers still go to the server immediately; nothing is shown as saved until it is */
  }
}

const REASON: Record<string, string> = {
  stale: "A newer answer from another tab or device is already saved.",
  invalid: "This answer couldn't be accepted.",
  late: "This answer reached the server after the time limit, so it wasn't counted.",
  finalised: "The test had already been submitted.",
  locked: "This question has been checked and can't be changed.",
  conflict: "This change clashed with an earlier one and wasn't applied.",
};

const noopSubscribe = () => () => {};

export function AttemptRunner({ attempt }: { attempt: PracticeAttempt }) {
  const router = useRouter();
  const total = attempt.items.length;
  const assetUrl = (v: string) => `/practice/attempt/${attempt.id}/assets/${v}`; // QUESTION-DIAGRAMS-01
  const [current, setCurrent] = useState(1);
  const [items, setItems] = useState<Record<number, ItemState>>(() => {
    const out: Record<number, ItemState> = {};
    for (const it of attempt.items) out[it.position] = { option: null, status: "empty", revision: 0 };
    for (const a of attempt.answers) out[a.position] = { option: a.option_id, status: a.option_id ? "saved" : "empty", revision: a.revision };
    return out;
  });
  const [revealed, setRevealed] = useState<Record<number, RevealResult>>({});
  const [locked, setLocked] = useState<Set<number>>(() => new Set(attempt.answers.filter((a) => a.revealed).map((a) => a.position)));
  // P11.S3.T2 (FLAGS-01): questions to come back to, kept with the attempt so a refresh or another device keeps them.
  const [flagged, setFlagged] = useState<Set<number>>(() => new Set(attempt.flagged ?? []));
  const [flagError, setFlagError] = useState<string | null>(null);
  const [connection, setConnection] = useState<"ok" | "retrying">("ok");
  // ANSWER-STATES-01: questions whose change a request is carrying now, and those whose last send failed.
  const [sending, setSending] = useState<ReadonlySet<number>>(() => new Set());
  const [failed, setFailed] = useState<ReadonlySet<number>>(() => new Set());
  // P10.S1.T3: another signed-in device holds this attempt; nothing is sent from here until the learner chooses.
  const [elsewhere, setElsewhere] = useState(attempt.held_elsewhere === true);
  const [moving, setMoving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const queue = useRef<Op[]>([]);
  const inflight = useRef<Promise<void> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelay = useRef(2000);
  const restored = useRef(false);
  const flushRef = useRef<() => Promise<void>>(() => Promise.resolve());

  // Clock: display only. The server's locked database time decides what is admitted. The offset to the server clock
  // is measured on the first tick (never during render); until then no countdown is shown.
  const offset = useRef<number | null>(null);
  const deadline = attempt.deadline_at ? new Date(attempt.deadline_at).getTime() : null;
  const cutoff = attempt.cutoff_at ? new Date(attempt.cutoff_at).getTime() : null;
  const [now, setNow] = useState<number | null>(null);
  const closed = deadline !== null && now !== null && now >= deadline;

  // Unacknowledged operations persisted on this device (read after hydration; null on the server).
  const storedRaw = useSyncExternalStore(noopSubscribe, () => readRaw(attempt.id), () => null);
  const view = useMemo(() => {
    const v = { ...items };
    for (const o of parseStored(storedRaw).ops) {
      const cur = v[o.position];
      // A stored change this page didn't make itself came from an earlier session: unacknowledged, so "pending".
      if (!cur || o.revision >= cur.revision) v[o.position] = { option: o.option_id, status: "pending", revision: o.revision, restored: cur?.status !== "pending" };
    }
    return v;
  }, [items, storedRaw]);

  const persist = useCallback(() => {
    const prev = readStored(attempt.id);
    writeStored(attempt.id, { ...prev, ops: queue.current });
  }, [attempt.id]);

  const apply = useCallback((results: AnswerOpResult[]) => {
    const done = new Set(results.map((r) => r.op_id));
    queue.current = queue.current.filter((o) => !done.has(o.op_id));
    setItems((prev) => {
      const next = { ...prev };
      for (const r of results) {
        const latestPending = queue.current.filter((o) => o.position === r.position).length > 0;
        const cur = next[r.position];
        if (!cur || latestPending) continue; // a newer local change is still on its way
        if (r.disposition === "accepted") {
          next[r.position] = { option: r.option_id ?? null, status: r.option_id ? "saved" : "empty", revision: r.revision };
        } else if (cur.revision <= r.revision) {
          next[r.position] = { ...cur, status: "rejected", reason: REASON[r.disposition] ?? "Not saved." };
        }
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
    const positions = new Set(batch.map((o) => o.position));
    setSending(positions);
    inflight.current = (async () => {
      const out = await reach(() => saveAnswers(attempt.id, batch), { kind: "error", message: OFFLINE } as const);
      if (out.kind === "elsewhere") {
        setElsewhere(true); // keep the queue; no automatic retry tug-of-war between devices
        setFailed((f) => new Set([...f, ...positions]));
      } else if (out.kind === "error") {
        setFailed((f) => new Set([...f, ...positions]));
        setConnection("retrying");
        const delay = retryDelay.current;
        retryDelay.current = Math.min(15_000, delay * 2);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => void flushRef.current(), delay + Math.random() * 500);
      } else {
        retryDelay.current = 2000;
        setConnection("ok");
        setFailed((f) => new Set([...f].filter((p) => !positions.has(p))));
        apply(out.results);
        persist();
        if (out.kind === "finalised" || (out.kind === "ok" && out.status !== "active")) router.refresh();
      }
    })();
    try {
      await inflight.current;
    } finally {
      inflight.current = null;
      setSending(new Set());
    }
    if (queue.current.length > 0 && retryDelay.current === 2000) void flushRef.current();
  }, [apply, attempt.id, persist, router]);

  useEffect(() => {
    flushRef.current = flush;
  }, [flush]);

  // Restore unacknowledged work from this device (shown as pending through `view`) and re-send it.
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    const stored = readStored(attempt.id);
    if (stored.ops.length > 0) {
      queue.current = stored.ops;
      void flush();
    }
  }, [attempt.id, flush]);

  // Send again as soon as the browser is back online. A separate effect, so it is always registered (the restore
  // above runs once even when React runs effects twice in development).
  useEffect(() => {
    const online = () => void flushRef.current();
    window.addEventListener("online", online);
    return () => window.removeEventListener("online", online);
  }, []);

  // Ticking clock, pre-flush at D − 5 s, flush at D, and pick up the server's expiry after C.
  const preFlushed = useRef(false);
  useEffect(() => {
    if (deadline === null) return;
    const id = setInterval(() => {
      offset.current ??= new Date(attempt.server_now).getTime() - Date.now();
      const t = Date.now() + offset.current;
      setNow(t);
      if (!preFlushed.current && t >= deadline - PRE_FLUSH_MS) {
        preFlushed.current = true;
        void flush();
      }
      if (cutoff !== null && t > cutoff + 1500) {
        clearInterval(id);
        void flush().then(() => router.refresh());
      }
    }, 500);
    return () => clearInterval(id);
  }, [attempt.server_now, cutoff, deadline, flush, router]);

  useEffect(() => {
    if (closed) void flush(); // editing closes at D; queued revisions still go out (admitted until C)
  }, [closed, flush]);

  function choose(position: number, option: string | null) {
    if (closed || submitting || locked.has(position)) return;
    const cur = view[position];
    const pendingMax = Math.max(0, ...queue.current.filter((o) => o.position === position).map((o) => o.revision));
    const revision = Math.max(cur?.revision ?? 0, pendingMax) + 1;
    const op: Op = { op_id: crypto.randomUUID(), position, revision, option_id: option };
    queue.current = [...queue.current, op];
    persist();
    setItems((prev) => ({ ...prev, [position]: { option, status: "pending", revision } }));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(), DEBOUNCE_MS);
  }

  async function toggleFlag(position: number) {
    if (closed || submitting) return;
    const before = flagged;
    const next = new Set(before);
    if (next.has(position)) next.delete(position);
    else next.add(position);
    setFlagged(next); // shown at once; put back if the server refuses
    setFlagError(null);
    const out = await reach(() => setFlags(attempt.id, [...next]), { ok: false, elsewhere: false, message: OFFLINE } as const);
    if (out.ok) {
      setFlagged(new Set(out.flagged));
      return;
    }
    setFlagged(before);
    if (out.elsewhere) setElsewhere(true);
    else setFlagError(out.message);
  }

  async function check(position: number) {
    await flush();
    const res = await reach(() => revealItem(attempt.id, position), { ok: false, message: OFFLINE } as const);
    if (res.ok) {
      setRevealed((r) => ({ ...r, [position]: res.data }));
      setLocked((l) => new Set(l).add(position));
    }
  }

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    if (timer.current) clearTimeout(timer.current);
    if (inflight.current) await inflight.current;
    const stored = readStored(attempt.id);
    const key = stored.submitKey ?? crypto.randomUUID().replaceAll("-", "");
    writeStored(attempt.id, { ops: queue.current, submitKey: key }); // retries reuse the same submission key
    const out = await reach(() => submitAttempt(attempt.id, key, queue.current), { kind: "error", message: OFFLINE } as const);
    if (out.kind === "elsewhere") setElsewhere(true);
    if (out.kind === "error" || out.kind === "elsewhere") {
      setSubmitting(false);
      setSubmitError(out.message);
      // Submitting stopped the retry timer: start it again, so unsent answers keep going out while the learner waits.
      if (out.kind === "error" && queue.current.length > 0) timer.current = setTimeout(() => void flushRef.current(), retryDelay.current);
      return;
    }
    writeStored(attempt.id, { ops: [] });
    router.replace(`/practice/attempt/${attempt.id}/result`); // Back never returns into a submitted test
  }

  const shown = (position: number): AnswerState => {
    const st = view[position];
    return answerState(st.status, { sending: sending.has(position), held: !!st.restored || failed.has(position) || connection === "retrying" || elsewhere });
  };
  const answered = Object.values(view).filter((i) => i.option !== null).length;
  const pending = Object.values(view).filter((i) => i.status === "pending").length;
  const item = attempt.items.find((i) => i.position === current)!;
  const state = view[current];
  const remaining = deadline !== null && now !== null ? Math.max(0, deadline - now) : null;

  async function moveHere() {
    setMoving(true);
    const out = await reach(() => continueHere(attempt.id), { ok: false, message: OFFLINE });
    setMoving(false);
    if (!out.ok) {
      setSubmitError(out.message ?? null);
      return;
    }
    setElsewhere(false);
    router.refresh(); // answers saved on the other device appear; this device's unsent changes are sent next
    void flushRef.current();
  }

  return (
    <div className="space-y-6">
      {elsewhere && (
        <div role="alert" className="space-y-2 rounded-xl border border-warn/40 bg-warn-soft p-4 text-sm">
          <p className="font-medium">This test is open on another device.</p>
          <p>
            Only one device can answer at a time. Anything you change here stays on this device and isn&apos;t sent until you
            continue here. The other device will then have to do the same.
          </p>
          <button
            type="button"
            onClick={() => void moveHere()}
            disabled={moving}
            className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
          >
            {moving ? "Moving…" : "Continue here"}
          </button>
        </div>
      )}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">
          Question {current} of {total}
        </h1>
        <div className="flex items-center gap-4 text-sm">
          <span role="status" aria-live="polite" className={connection === "retrying" ? "text-warn" : "text-muted"}>
            {connection === "retrying"
              ? "Offline: answers are kept on this device and will be sent again"
              : pending > 0
                ? `Saving ${pending}…`
                : `${answered} answered · all saved`}
          </span>
          {connection === "retrying" && <HelpLink slug="practice-timer-and-saving">About saving</HelpLink>}
          {deadline !== null && (
            <span aria-label="Time remaining" className={`font-mono tabular-nums ${remaining !== null && remaining < 60_000 ? "text-danger" : ""}`}>
              {remaining === null
                ? "--:--"
                : closed
                  ? "Time is up"
                  : `${Math.floor(remaining / 60_000)}:${String(Math.floor((remaining % 60_000) / 1000)).padStart(2, "0")}`}
            </span>
          )}
        </div>
      </header>

      <nav aria-label="Questions" className="flex flex-wrap gap-1.5">
        {attempt.items.map((it) => {
          const s = shown(it.position);
          return (
            <button
              key={it.position}
              type="button"
              onClick={() => setCurrent(it.position)}
              aria-current={it.position === current ? "step" : undefined}
              aria-label={`Question ${it.position}: ${PALETTE_LABEL[s]}${flagged.has(it.position) ? ", flagged" : ""}`}
              className={`relative h-9 w-9 rounded-md border text-sm ${TONE[s]} ${it.position === current ? "ring-2 ring-accent" : ""}`}
            >
              {it.position}
              {flagged.has(it.position) && (
                <span aria-hidden="true" className="absolute -top-1.5 -right-1.5 rounded-full bg-warn px-1 text-[10px] leading-4 text-white dark:text-background">
                  ⚑
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <section aria-labelledby="q-heading" className="space-y-4 rounded-xl border border-border bg-surface p-5">
        <h2 id="q-heading" className="sr-only">
          Question {current}
        </h2>
        {item.passage && (
          <section aria-label="Passage" className="rounded-lg border border-border bg-surface-muted px-4 py-3">
            <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">Read the passage</p>
            <LessonBlocks blocks={item.passage.blocks as { type: string }[]} headingOffset={2} assetUrl={assetUrl} />
          </section>
        )}
        <LessonBlocks blocks={item.stem as { type: string }[]} headingOffset={1} assetUrl={assetUrl} />
        <fieldset disabled={closed || submitting || locked.has(current)} className="space-y-2">
          <legend className="sr-only">Options for question {current}</legend>
          {item.options.map((o, idx) => {
            const reveal = revealed[current];
            const mark = reveal ? (o.id === reveal.correct_option_id ? "border-ok bg-ok-soft" : o.id === reveal.chosen ? "border-danger bg-danger-soft" : "") : "";
            return (
              <label key={o.id} className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 ${mark || (state.option === o.id ? "border-accent bg-accent-soft" : "border-border")}`}>
                <input type="radio" name={`q${current}`} value={o.id} checked={state.option === o.id} onChange={() => choose(current, o.id)} className="mt-1" />
                <span className="w-5 font-medium text-muted">{String.fromCharCode(65 + idx)}</span>
                <span className="flex-1">
                  <LessonBlocks blocks={o.blocks as { type: string }[]} headingOffset={2} assetUrl={assetUrl} />
                </span>
              </label>
            );
          })}
        </fieldset>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {state.option !== null && !closed && !locked.has(current) && (
            <button type="button" onClick={() => choose(current, null)} className="text-accent underline-offset-2 hover:underline">
              Clear answer
            </button>
          )}
          {!closed && (
            <button
              type="button"
              onClick={() => void toggleFlag(current)}
              aria-pressed={flagged.has(current)}
              disabled={submitting || elsewhere}
              className={`rounded-lg border px-3 py-1.5 disabled:opacity-60 ${flagged.has(current) ? "border-warn bg-warn-soft" : "border-border hover:border-accent"}`}
            >
              {flagged.has(current) ? "⚑ Flagged for review" : "Flag for review"}
            </button>
          )}
          {flagError && (
            <span role="alert" className="text-danger">
              {flagError}
            </span>
          )}
          {attempt.feedback_mode === "immediate" && state.status === "saved" && state.option !== null && !revealed[current] && !locked.has(current) && (
            <button type="button" onClick={() => void check(current)} className="rounded-lg border border-border px-3 py-1.5 hover:border-accent">
              Check answer
            </button>
          )}
          <span className={shown(current) === "rejected" ? "text-danger" : shown(current) === "pending" ? "text-warn" : "text-muted"}>
            {stateLine(shown(current), { elsewhere, reason: state.reason })}
          </span>
        </div>
        {revealed[current] && (
          <div role="status" className="space-y-2 rounded-lg border border-border bg-surface-muted p-3 text-sm">
            <p className="font-semibold">{revealed[current].correct ? "Correct" : "Not quite"}</p>
            <LessonBlocks blocks={((revealed[current].explanation as { correct?: unknown[] }).correct ?? []) as { type: string }[]} headingOffset={2} assetUrl={assetUrl} />
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          <button type="button" disabled={current === 1} onClick={() => setCurrent(current - 1)} className="rounded-lg border border-border bg-surface px-4 py-2 disabled:opacity-40">
            ← Previous
          </button>
          <button type="button" disabled={current === total} onClick={() => setCurrent(current + 1)} className="rounded-lg border border-border bg-surface px-4 py-2 disabled:opacity-40">
            Next →
          </button>
        </div>
        <button type="button" onClick={() => setConfirming(true)} disabled={submitting} className="rounded-lg bg-accent px-5 py-2.5 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
          Finish test
        </button>
      </div>

      {confirming && (
        <section role="dialog" aria-modal="false" aria-labelledby="confirm-h" className="space-y-3 rounded-xl border border-accent bg-surface p-5">
          <h2 id="confirm-h" className="font-semibold">
            Submit your test?
          </h2>
          <ul className="text-sm">
            <li>{answered} answered</li>
            <li>{total - answered} not answered</li>
            {pending > 0 && <li>{pending} still being saved; they will be sent with your submission</li>}
            {flagged.size > 0 && <li>{flagged.size} flagged for review</li>}
          </ul>
          {flagged.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">Go back to a flagged question:</span>
              {[...flagged]
                .sort((x, y) => x - y)
                .map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => {
                      setCurrent(p);
                      setConfirming(false);
                    }}
                    className="rounded-md border border-warn bg-warn-soft px-2 py-1"
                  >
                    Question {p}
                  </button>
                ))}
            </div>
          )}
          <p className="text-sm text-muted">After you submit you can&apos;t change any answer.</p>
          {submitError && (
            <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
              {submitError}
            </p>
          )}
          <div className="flex gap-2">
            <button type="button" onClick={() => void submit()} disabled={submitting} className="rounded-lg bg-accent px-4 py-2 font-medium text-white disabled:opacity-60 dark:text-background">
              {submitting ? "Submitting…" : submitError ? "Try again" : "Submit"}
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
                setSubmitError(null); // an old failure isn't shown again when the dialog reopens
              }}
              disabled={submitting}
              className="rounded-lg border border-border px-4 py-2"
            >
              Keep working
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
