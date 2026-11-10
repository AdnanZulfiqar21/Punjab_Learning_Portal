"use client";
// CHAPTER-MOCK-01 (owner, 2026-11-10): a chapter mock test as two tabs, "Question paper" (the Board paper layout: the
// objective part is answered here on a 20-minute timer and submitted; the subjective part is written on paper) and
// "Solution paper" (owner: how many MCQs were correct, the right answer of each wrong one, and a model answer for every
// short and long part).
import { useEffect, useRef, useState } from "react";
import type { Paper, PaperQuestion } from "@/lib/chapter-mocks";

const ROMAN = [
  "i",
  "ii",
  "iii",
  "iv",
  "v",
  "vi",
  "vii",
  "viii",
  "ix",
  "x",
  "xi",
  "xii",
  "xiii",
  "xiv",
  "xv",
];
const LETTER = ["A", "B", "C", "D"];

type Head = {
  part: string;
  className: string;
  subject: string;
  chapter: string;
};

function clock(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

function useTimer(seconds: number, onEnd?: () => void) {
  const [left, setLeft] = useState(seconds);
  const [running, setRunning] = useState(false);
  const end = useRef(onEnd);
  useEffect(() => {
    end.current = onEnd;
  });
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      setLeft((l) => {
        if (l > 1) return l - 1;
        clearInterval(id);
        setRunning(false);
        queueMicrotask(() => end.current?.());
        return 0;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [running]);
  return {
    left,
    running,
    start: () => setRunning(true),
    stop: () => setRunning(false),
  };
}

function PaperHead({
  head,
  kind,
  time,
  marks,
}: {
  head: Head;
  kind: string;
  time: string;
  marks: number;
}) {
  const cell = "border border-border px-3 py-1.5";
  return (
    <table className="w-full table-fixed border-collapse text-sm [overflow-wrap:anywhere]">
      <tbody>
        <tr>
          <td className={`${cell} font-semibold`} colSpan={2}>
            {head.part} ({head.className}) · Mock test
          </td>
          <td className={cell}>{head.chapter}</td>
        </tr>
        <tr>
          <td className={cell}>{head.subject}</td>
          <td className={`${cell} text-center font-semibold`}>{kind}</td>
          <td className={cell}>MAXIMUM MARKS: {marks}</td>
        </tr>
        <tr>
          <td className={cell} colSpan={3}>
            TIME ALLOWED: {time}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function Answer({ q }: { q: PaperQuestion }) {
  const a = q.answer;
  return (
    <div className="space-y-2 rounded-inner bg-accent-soft/60 px-4 py-3 text-[15px] leading-relaxed">
      {a.text && !a.steps && <p className="whitespace-pre-line">{a.text}</p>}
      {a.table && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {a.table.header.map((h) => (
                  <th
                    key={h}
                    className="border border-border bg-surface px-2 py-1.5 text-left align-top"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {a.table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td
                      key={j}
                      className="border border-border px-2 py-1.5 align-top"
                    >
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {a.steps && (
        <>
          {a.text && <p className="text-muted">{a.text}</p>}
          <ol className="list-decimal space-y-1 pl-5">
            {a.steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </>
      )}
      {a.final && <p className="font-semibold">{a.final}</p>}
    </div>
  );
}

function QHead({ title, marks }: { title: string; marks: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b-2 border-border pt-4 pb-2">
      <h3 className="font-display text-lg font-semibold">{title}</h3>
      <span className="font-display text-sm font-semibold whitespace-nowrap">
        {marks}
      </span>
    </div>
  );
}

function Row({
  label,
  q,
  marks,
  solved,
}: {
  label: string;
  q: PaperQuestion;
  marks?: number;
  solved: boolean;
}) {
  return (
    <div className="grid grid-cols-[3.25rem_1fr_auto] gap-x-2 gap-y-2 border-b border-border/70 py-3">
      <span className="font-semibold text-muted">{label}</span>
      <p>{q.q}</p>
      <span className="font-display text-sm font-semibold text-muted">
        {marks ?? ""}
      </span>
      {solved && (
        <div className="col-span-3 sm:col-start-2">
          <Answer q={q} />
        </div>
      )}
    </div>
  );
}

function Subjective({ paper, solved }: { paper: Paper; solved: boolean }) {
  const p = paper.pattern;
  const total = p.long.parts[0] + p.long.parts[1];
  return (
    <div>
      <p className="pt-5 text-center font-display font-bold tracking-[0.08em]">
        SECTION-I
      </p>
      {paper.short.map((s) => (
        <div key={s.no}>
          <QHead
            title={`${s.no}. Write the answers of any ${s.attempt === 8 ? "eight" : s.attempt === 6 ? "six" : s.attempt} parts.`}
            marks={`${s.attempt} × 2 = ${s.attempt * 2}`}
          />
          {s.parts.map((q, i) => (
            <Row key={i} label={`(${ROMAN[i]})`} q={q} solved={solved} />
          ))}
        </div>
      ))}
      <p className="pt-6 text-center font-display font-bold tracking-[0.08em]">
        SECTION-II
      </p>
      <QHead
        title={`NOTE: Write answers of any ${p.long.attempt === 3 ? "three" : p.long.attempt} questions.`}
        marks={`${p.long.attempt} × ${total} = ${p.long.attempt * total}`}
      />
      {paper.long.map((pr, i) => (
        <div key={i}>
          <Row
            label={`${i + 5}.(a)`}
            q={pr.a}
            marks={pr.a.marks}
            solved={solved}
          />
          <Row label="(b)" q={pr.b} marks={pr.b.marks} solved={solved} />
        </div>
      ))}
    </div>
  );
}

export function MockPaper({ paper, head }: { paper: Paper; head: Head }) {
  const [tab, setTab] = useState<"question" | "solution">("question");
  const [chosen, setChosen] = useState<(number | null)[]>(() =>
    paper.mcqs.map(() => null),
  );
  const [checked, setChecked] = useState(false);
  const p = paper.pattern;
  const objective = useTimer(p.objectiveMinutes * 60, () => {
    setChecked(true);
    setTab("solution");
  });
  const subjective = useTimer(p.subjectiveMinutes * 60);
  const subjMarks =
    p.short.reduce((a, s) => a + s.attempt * 2, 0) +
    p.long.attempt * (p.long.parts[0] + p.long.parts[1]);
  const right = paper.mcqs.filter((q, i) => chosen[i] === q.key).length;
  const blank = chosen.filter((c) => c === null).length;
  const wrong = paper.mcqs.length - right - blank;
  const submit = () => {
    objective.stop();
    setChecked(true);
    setTab("solution");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const subjTime = `${Math.floor(p.subjectiveMinutes / 60)}.${String(p.subjectiveMinutes % 60).padStart(2, "0")} Hours`;
  const tabBtn =
    "min-h-12 flex-1 rounded-full px-4 text-[15px] font-semibold transition-colors";
  const btn =
    "inline-flex min-h-11 items-center rounded-full px-5 text-sm font-semibold transition-colors disabled:opacity-45";

  return (
    <div className="space-y-5">
      <div
        role="tablist"
        aria-label="Mock test"
        className="glass flex gap-1 rounded-full p-1"
      >
        {(
          [
            ["question", "Question paper"],
            ["solution", "Solution paper"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            role="tab"
            type="button"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            className={`${tabBtn} ${tab === k ? "bg-foreground text-background shadow-glass" : "text-muted hover:bg-surface-muted hover:text-foreground"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <section
        className="glass space-y-4 rounded-card px-5 py-6 sm:px-8"
        aria-label="Objective"
      >
        <PaperHead
          head={head}
          kind="OBJECTIVE"
          time={`${p.objectiveMinutes} Minutes`}
          marks={p.mcqs}
        />
        <p className="text-sm text-muted">
          Q.No.1 — You have four choices for each objective type question as A,
          B, C and D. Choose the one you think is correct. Each question carries
          1 mark.
        </p>
        {tab === "question" ? (
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="rounded-inner bg-accent-soft px-3 py-1.5 font-display text-xl font-bold text-accent tabular-nums"
              aria-label="Time left"
            >
              {clock(objective.left)}
            </span>
            <button
              type="button"
              className={`${btn} bg-foreground text-background`}
              disabled={objective.running || checked}
              onClick={objective.start}
            >
              Start
            </button>
            <button
              type="button"
              className={`${btn} border border-border`}
              disabled={checked}
              onClick={submit}
            >
              Submit MCQs
            </button>
            {checked && (
              <span className="text-sm text-muted" role="status">
                Submitted. Open the Solution paper to see your result.
              </span>
            )}
          </div>
        ) : checked ? (
          <div className="grid grid-cols-3 gap-2 text-center" role="status">
            <div className="rounded-inner bg-ok-soft px-3 py-3">
              <p className="font-display text-2xl font-bold text-ok">{right}</p>
              <p className="text-sm font-semibold">Correct</p>
            </div>
            <div className="rounded-inner bg-danger-soft px-3 py-3">
              <p className="font-display text-2xl font-bold text-danger">
                {wrong}
              </p>
              <p className="text-sm font-semibold">Wrong</p>
            </div>
            <div className="rounded-inner bg-surface-muted px-3 py-3">
              <p className="font-display text-2xl font-bold">{blank}</p>
              <p className="text-sm font-semibold">Not attempted</p>
            </div>
            <p className="col-span-3 font-display text-lg font-bold">
              Your score: {right} / {paper.mcqs.length}
            </p>
          </div>
        ) : (
          <p className="rounded-inner bg-surface-muted px-4 py-3 text-sm">
            Answer the MCQs in the Question paper and press Submit MCQs: your
            correct and wrong answers are shown here.
          </p>
        )}
        <ol className="divide-y divide-border/70">
          {paper.mcqs.map((q, i) => {
            const mine = chosen[i];
            const solution = tab === "solution";
            const verdict =
              !solution || !checked
                ? null
                : mine === null
                  ? "blank"
                  : mine === q.key
                    ? "right"
                    : "wrong";
            return (
              <li key={i} className="space-y-2 py-3">
                <p className="flex gap-3 font-medium">
                  <span className="inline-grid size-7 shrink-0 place-items-center rounded-lg bg-accent-soft font-display text-sm text-accent">
                    {i + 1}
                  </span>
                  <span className="flex-1">{q.q}</span>
                  {verdict && (
                    <span
                      className={`shrink-0 self-start rounded-full px-2.5 py-0.5 text-xs font-bold ${verdict === "right" ? "bg-ok-soft text-ok" : verdict === "wrong" ? "bg-danger-soft text-danger" : "bg-surface-muted text-muted"}`}
                    >
                      {verdict === "right"
                        ? "Correct"
                        : verdict === "wrong"
                          ? "Wrong"
                          : "Not attempted"}
                    </span>
                  )}
                </p>
                <div className="grid gap-2 sm:grid-cols-2 sm:pl-10">
                  {(q.options ?? []).map((o, j) => {
                    const isKey = solution && j === q.key;
                    const isWrong =
                      solution && checked && mine === j && j !== q.key;
                    return (
                      <label
                        key={j}
                        className={`flex min-h-11 items-start gap-2 rounded-inner border px-3 py-2 ${isKey ? "border-ok bg-ok-soft" : isWrong ? "border-danger bg-danger-soft" : "border-border"} ${!solution && !checked ? "cursor-pointer" : ""}`}
                      >
                        {!solution && (
                          <input
                            type="radio"
                            name={`mcq-${i}`}
                            className="mt-1.5"
                            disabled={checked}
                            checked={mine === j}
                            onChange={() =>
                              setChosen((c) =>
                                c.map((x, k) => (k === i ? j : x)),
                              )
                            }
                          />
                        )}
                        <span className="font-semibold text-muted">
                          {LETTER[j]}
                        </span>
                        <span className="flex-1">{o}</span>
                        {solution && checked && mine === j && (
                          <span className="shrink-0 text-xs font-bold">
                            Your answer
                          </span>
                        )}
                      </label>
                    );
                  })}
                </div>
                {solution && (
                  <p className="text-sm sm:pl-10">
                    <span className="font-semibold text-ok">
                      Correct answer: {LETTER[q.key ?? 0]}
                    </span>
                    {verdict === "wrong" && (
                      <span className="text-danger">
                        {" "}
                        · you chose {LETTER[mine ?? 0]}
                      </span>
                    )}
                    {q.answer.text && (
                      <span className="text-muted"> — {q.answer.text}</span>
                    )}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <section
        className="glass space-y-2 rounded-card px-5 py-6 sm:px-8"
        aria-label="Subjective"
      >
        <PaperHead
          head={head}
          kind="SUBJECTIVE"
          time={subjTime}
          marks={subjMarks}
        />
        {tab === "question" ? (
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <span
              className="rounded-inner bg-accent-soft px-3 py-1.5 font-display text-xl font-bold text-accent tabular-nums"
              aria-label="Time left"
            >
              {clock(subjective.left)}
            </span>
            <button
              type="button"
              className={`${btn} bg-foreground text-background`}
              disabled={subjective.running}
              onClick={subjective.start}
            >
              Start
            </button>
            <span className="text-sm text-muted">
              Write the answers on paper, then open the Solution paper to check
              them.
            </span>
          </div>
        ) : (
          <p className="pt-2 text-sm text-muted">
            Model answers for every part. In the examination you answer only the
            parts asked for.
          </p>
        )}
        <Subjective paper={paper} solved={tab === "solution"} />
      </section>
    </div>
  );
}
