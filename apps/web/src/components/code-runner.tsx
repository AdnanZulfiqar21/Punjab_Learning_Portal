"use client";

// CODE-RUNNER-01: "Run karein" under a printed Python program in the Roman Urdu tab. The program runs in the student's
// own browser (public/py-runner.js, Pyodide); nothing is sent anywhere. A student may change only the values of the
// program's variables (lib/code-vars.ts) and answer its input() questions; the printed program itself never changes.
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { editableVars, inputPrompts, isPlainValue, withValues } from "@/lib/code-vars";

const LIMIT_MS = 5000; // a program that runs longer (a loop that never ends) is stopped

type Result = { output: string; error: string | null; timedOut?: boolean };
type Phase = "idle" | "loading" | "running";
type Message = { type: "loading" | "started" | "done" | "failed" | "crashed"; output?: string; error?: string | null };

export function CodeRunner({ code }: { code: string }) {
  const id = useId();
  const vars = useMemo(() => editableVars(code), [code]);
  const prompts = useMemo(() => inputPrompts(code), [code]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [answers, setAnswers] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<Result | null>(null);
  const worker = useRef<Worker | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handler = useRef<(m: Message) => void>(() => undefined);

  useEffect(
    () => () => {
      worker.current?.terminate();
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const changed = Object.entries(values).some(([key, v]) => vars.find((x) => x.key === key)?.value !== v);
  const invalid = Object.values(values).some((v) => !isPlainValue(v));

  function stop(next: Result | null) {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setPhase("idle");
    if (next) setResult(next);
  }

  // The worker stays alive between runs (Python loads once); each run sets what its messages do.
  function getWorker(): Worker {
    if (!worker.current) {
      const w = new Worker("/py-runner.js", { type: "module" });
      w.addEventListener("message", (e: MessageEvent<Message>) => handler.current(e.data));
      w.addEventListener("error", () => handler.current({ type: "crashed" }));
      worker.current = w;
    }
    return worker.current;
  }

  function endWorker() {
    worker.current?.terminate();
    worker.current = null;
  }

  function run() {
    if (phase !== "idle" || invalid) return;
    handler.current = (m) => {
      if (m.type === "loading") setPhase("loading");
      else if (m.type === "started") {
        setPhase("running");
        timer.current = setTimeout(() => {
          // The only way to stop Python mid-loop: end the worker. The next run starts a fresh one.
          endWorker();
          stop({ output: "", error: null, timedOut: true });
        }, LIMIT_MS);
      } else if (m.type === "done") stop({ output: m.output ?? "", error: m.error ?? null });
      else {
        endWorker();
        stop({ output: "", error: m.error || "Python load nahi ho saka. Internet check kar ke dobara koshish karein." });
      }
    };
    setResult(null);
    setPhase("loading");
    getWorker().postMessage({ code: withValues(code, vars, values), stdin: prompts.map((_, i) => answers[i] ?? "") });
  }

  const busy = phase !== "idle";
  return (
    <section className="space-y-3 rounded-xl border border-accent/40 bg-accent-soft/40 px-4 py-3" aria-label="Program chala kar dekhein">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={run}
          disabled={busy || invalid}
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background">
          <span aria-hidden>▶</span> {busy ? "Chal raha hai…" : "Run karein"}
        </button>
        {changed && (
          <button
            type="button"
            onClick={() => setValues({})}
            disabled={busy}
            className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-muted hover:text-foreground">
            Kitab wali values wapas
          </button>
        )}
        <span className="text-xs text-muted">Program aap ke browser mein chalta hai.</span>
      </div>

      {vars.length > 0 && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Values badal kar dekhein</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {vars.map((v) => {
              const value = values[v.key] ?? v.value;
              const bad = !isPlainValue(value);
              return (
                <label key={v.key} className="flex items-center gap-2 font-mono text-sm">
                  <span className="code-variable shrink-0">{v.label}</span>
                  <span aria-hidden>=</span>
                  <input
                    value={value}
                    onChange={(e) => setValues((s) => ({ ...s, [v.key]: e.target.value }))}
                    aria-invalid={bad}
                    aria-describedby={bad ? `${id}-bad` : undefined}
                    spellCheck={false}
                    className={`min-w-0 flex-1 rounded-md border bg-surface px-2 py-1 ${bad ? "border-danger" : "border-border"}`}
                  />
                </label>
              );
            })}
          </div>
          {invalid && (
            <p id={`${id}-bad`} className="text-sm text-danger">
              Sirf value likhein: number (jaise 7), text quotes mein (jaise &quot;Ali&quot;), True/False, ya list (jaise [1, 2]).
            </p>
          )}
        </fieldset>
      )}

      {prompts.length > 0 && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Program aap se poochega (input)</legend>
          {prompts.map((p, i) => (
            <label key={i} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono">{p || `Input ${i + 1}`}</span>
              <input
                value={answers[i] ?? ""}
                onChange={(e) => setAnswers((s) => Object.assign([...s], { [i]: e.target.value }))}
                className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1 font-mono"
              />
            </label>
          ))}
        </fieldset>
      )}

      {(busy || result) && (
        <div className="space-y-1" aria-live="polite">
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">Output</p>
          {phase === "loading" ? (
            <p className="text-sm text-muted">Python load ho raha hai… pehli dafa thora waqt lagta hai.</p>
          ) : phase === "running" ? (
            <p className="text-sm text-muted">Program chal raha hai…</p>
          ) : result?.timedOut ? (
            <p className="text-sm text-danger">Program 5 second mein khatam nahi hua, is liye rok diya (shayad loop kabhi khatam nahi hota).</p>
          ) : (
            <>
              {result?.output ? (
                <pre className="max-h-72 overflow-auto rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm whitespace-pre-wrap">{result.output}</pre>
              ) : !result?.error ? (
                <p className="text-sm text-muted">(Program ne kuch print nahi kiya.)</p>
              ) : null}
              {result?.error && (
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-danger">Program mein ghalti (error):</p>
                  <pre className="max-h-48 overflow-auto rounded-lg bg-danger-soft px-3 py-2 font-mono text-xs whitespace-pre-wrap text-danger">{result.error}</pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
