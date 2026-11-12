// CHAPTER-MOCK-01 / BOOK-MOCK-01 on the phone (owner, 2026-11-13: "sb sat sat banaty jao"): a mock test as two tabs, as
// on the web. "Question paper" is the Board paper layout: the MCQs are answered here on the objective timer and
// submitted; the short and long answers are written on paper. "Solution paper" shows how many MCQs were correct, the
// right answer of each wrong one, and a model answer for every short and long part.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Pressable, Text, View } from "react-native";

import { Button } from "@/components/form";
import { Segmented, T } from "@/components/ui";
import { HeadingFont, Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import type { Paper, PaperQuestion } from "@/lib/chapter-mocks";

const ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv"];
const LETTER = ["A", "B", "C", "D", "E"];
const WORDS: Record<number, string> = { 3: "three", 6: "six", 8: "eight", 9: "nine" };

export type PaperHead = { part: string; className: string; subject: string; scope: string };

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
        setTimeout(() => end.current?.(), 0);
        return 0;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [running]);
  return { left, running, start: () => setRunning(true), stop: () => setRunning(false) };
}

function Head({ head, kind, time, marks }: { head: PaperHead; kind: string; time: string; marks: number }) {
  const c = useTheme();
  const cell = { borderWidth: 1, borderColor: c.border, padding: Space.sm, flex: 1 } as const;
  const t = { fontSize: 13, color: c.text } as const;
  return (
    <View>
      <View style={{ flexDirection: "row" }}>
        <View style={cell}>
          <Text style={[t, { fontWeight: "700" }]}>{`${head.part} (${head.className}) · Mock test`}</Text>
        </View>
        <View style={cell}>
          <Text style={t}>{head.scope}</Text>
        </View>
      </View>
      <View style={{ flexDirection: "row" }}>
        <View style={cell}>
          <Text style={t}>{head.subject}</Text>
        </View>
        <View style={cell}>
          <Text style={[t, { fontWeight: "700", textAlign: "center" }]}>{kind}</Text>
        </View>
        <View style={cell}>
          <Text style={t}>{`MAXIMUM MARKS: ${marks}`}</Text>
        </View>
      </View>
      <View style={cell}>
        <Text style={t}>{`TIME ALLOWED: ${time}`}</Text>
      </View>
    </View>
  );
}

function Answer({ q }: { q: PaperQuestion }) {
  const c = useTheme();
  const a = q.answer;
  return (
    <View style={{ gap: Space.sm, borderRadius: Radius.md, backgroundColor: c.accentSoft, padding: Space.md }}>
      {a.text ? <T style={a.steps ? { color: c.muted } : undefined}>{a.text}</T> : null}
      {a.table ? (
        <View style={{ borderWidth: 1, borderColor: c.border, borderRadius: Radius.sm, overflow: "hidden" }}>
          {[a.table.header, ...a.table.rows].map((row, i) => (
            <View key={i} style={{ flexDirection: "row", backgroundColor: i === 0 ? c.surface : "transparent" }}>
              {row.map((cellText, j) => (
                <View key={j} style={{ flex: 1, borderWidth: 0.5, borderColor: c.border, padding: Space.xs }}>
                  <Text style={{ fontSize: 13, color: c.text, fontWeight: i === 0 ? "700" : "400" }}>{cellText}</Text>
                </View>
              ))}
            </View>
          ))}
        </View>
      ) : null}
      {a.steps
        ? a.steps.map((s, i) => (
            <T key={i}>
              {`${i + 1}. ${s}`}
            </T>
          ))
        : null}
      {a.final ? <T style={{ fontWeight: "700" }}>{a.final}</T> : null}
    </View>
  );
}

function QHead({ title, marks }: { title: string; marks: string }) {
  const c = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", gap: Space.sm, borderBottomWidth: 2, borderColor: c.border, paddingTop: Space.md, paddingBottom: Space.xs }}>
      <Text style={{ flex: 1, fontFamily: HeadingFont.semibold, fontSize: 16, color: c.text }}>{title}</Text>
      <Text style={{ fontFamily: HeadingFont.semibold, fontSize: 14, color: c.text }}>{marks}</Text>
    </View>
  );
}

function Row({ label, q, marks, solved }: { label: string; q: PaperQuestion; marks?: number; solved: boolean }) {
  const c = useTheme();
  return (
    <View style={{ gap: Space.sm, borderBottomWidth: 1, borderColor: c.border, paddingVertical: Space.sm }}>
      <View style={{ flexDirection: "row", gap: Space.sm }}>
        <Text style={{ width: 44, fontWeight: "700", color: c.muted }}>{label}</Text>
        <T style={{ flex: 1 }}>{q.q}</T>
        {marks ? <Text style={{ fontWeight: "700", color: c.muted }}>{marks}</Text> : null}
      </View>
      {solved ? <Answer q={q} /> : null}
    </View>
  );
}

function Section({ children, label }: { children: ReactNode; label: string }) {
  const c = useTheme();
  return (
    <View accessibilityLabel={label} style={{ gap: Space.md, borderRadius: Radius.xl, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, padding: Space.md }}>
      {children}
    </View>
  );
}

export function MockPaper({ paper, head, onTop }: { paper: Paper; head: PaperHead; onTop?: () => void }) {
  const c = useTheme();
  const p = paper.pattern;
  const [tab, setTab] = useState<"question" | "solution">("question");
  const [chosen, setChosen] = useState<(number | null)[]>(() => paper.mcqs.map(() => null));
  const [checked, setChecked] = useState(false);
  const objective = useTimer(p.objectiveMinutes * 60, () => {
    setChecked(true);
    setTab("solution");
  });
  const subjective = useTimer(p.subjectiveMinutes * 60);
  const longTotal = p.long.parts.reduce((x: number, y) => x + y, 0);
  const subjMarks = p.short.reduce((a, s) => a + s.attempt * 2, 0) + p.long.attempt * longTotal;
  const right = paper.mcqs.filter((q, i) => chosen[i] === q.key).length;
  const blank = chosen.filter((x) => x === null).length;
  const wrong = paper.mcqs.length - right - blank;
  const solution = tab === "solution";
  const submit = () => {
    objective.stop();
    setChecked(true);
    setTab("solution");
    onTop?.();
  };
  const subjTime = `${Math.floor(p.subjectiveMinutes / 60)}.${String(p.subjectiveMinutes % 60).padStart(2, "0")} Hours`;
  const timerBox = (left: number, running: boolean, start: () => void, disabled: boolean) => (
    <View style={{ flexDirection: "row", alignItems: "center", gap: Space.sm, flexWrap: "wrap" }}>
      <View accessibilityLabel="Time left" style={{ borderRadius: Radius.md, backgroundColor: c.accentSoft, paddingHorizontal: Space.md, paddingVertical: Space.xs }}>
        <Text style={{ fontFamily: HeadingFont.bold, fontSize: 20, color: c.accent, fontVariant: ["tabular-nums"] }}>{clock(left)}</Text>
      </View>
      <Button label="Start" onPress={start} disabled={running || disabled} />
    </View>
  );

  return (
    <View style={{ gap: Space.lg }}>
      <Segmented
        label="Mock test"
        options={[
          ["question", "Question paper"],
          ["solution", "Solution paper"],
        ]}
        value={tab}
        onChange={(v) => setTab(v)}
      />

      <Section label="Objective">
        <Head head={head} kind="OBJECTIVE" time={`${p.objectiveMinutes} Minutes`} marks={p.mcqs} />
        <T variant="small" style={{ color: c.muted }}>
          Q.No.1 — You have four choices for each objective type question as A, B, C and D. Choose the one you think is correct. Each question carries 1 mark.
        </T>
        {!solution ? (
          <View style={{ gap: Space.sm }}>
            {timerBox(objective.left, objective.running, objective.start, checked)}
            <View style={{ alignSelf: "flex-start" }}>
              <Button variant="secondary" label="Submit MCQs" onPress={submit} disabled={checked} />
            </View>
            {checked ? <T variant="small" style={{ color: c.muted }}>Submitted. Open the Solution paper to see your result.</T> : null}
          </View>
        ) : checked ? (
          <View accessibilityRole="summary" style={{ gap: Space.sm }}>
            <View style={{ flexDirection: "row", gap: Space.sm }}>
              {(
                [
                  [right, "Correct", c.ok, c.okSoft],
                  [wrong, "Wrong", c.danger, c.dangerSoft],
                  [blank, "Not attempted", c.text, c.surfaceMuted],
                ] as const
              ).map(([n, label, fg, bg]) => (
                <View key={label} style={{ flex: 1, alignItems: "center", borderRadius: Radius.md, backgroundColor: bg, paddingVertical: Space.sm }}>
                  <Text style={{ fontFamily: HeadingFont.bold, fontSize: 22, color: fg }}>{n}</Text>
                  <Text style={{ fontSize: 13, fontWeight: "600", color: c.text, textAlign: "center" }}>{label}</Text>
                </View>
              ))}
            </View>
            <Text style={{ fontFamily: HeadingFont.bold, fontSize: 17, color: c.text, textAlign: "center" }}>
              {`Your score: ${right} / ${paper.mcqs.length}`}
            </Text>
          </View>
        ) : (
          <View style={{ borderRadius: Radius.md, backgroundColor: c.surfaceMuted, padding: Space.md }}>
            <T variant="small">Answer the MCQs in the Question paper and press Submit MCQs: your correct and wrong answers are shown here.</T>
          </View>
        )}

        {paper.mcqs.map((q, i) => {
          const mine = chosen[i];
          const verdict = !solution || !checked ? null : mine === null ? "blank" : mine === q.key ? "right" : "wrong";
          return (
            <View key={i} style={{ gap: Space.sm, borderTopWidth: 1, borderColor: c.border, paddingTop: Space.md }}>
              <View style={{ flexDirection: "row", gap: Space.sm }}>
                <View style={{ width: 28, height: 28, borderRadius: 8, alignItems: "center", justifyContent: "center", backgroundColor: c.accentSoft }}>
                  <Text style={{ color: c.accent, fontWeight: "700", fontSize: 13 }}>{i + 1}</Text>
                </View>
                <T style={{ flex: 1, fontWeight: "500" }}>{q.q}</T>
              </View>
              {verdict ? (
                <View
                  style={{
                    alignSelf: "flex-start",
                    borderRadius: Radius.pill,
                    paddingHorizontal: Space.sm,
                    paddingVertical: 2,
                    backgroundColor: verdict === "right" ? c.okSoft : verdict === "wrong" ? c.dangerSoft : c.surfaceMuted,
                  }}>
                  <Text style={{ fontSize: 12, fontWeight: "700", color: verdict === "right" ? c.ok : verdict === "wrong" ? c.danger : c.muted }}>
                    {verdict === "right" ? "Correct" : verdict === "wrong" ? "Wrong" : "Not attempted"}
                  </Text>
                </View>
              ) : null}
              {(q.options ?? []).map((o, j) => {
                const isKey = solution && j === q.key;
                const isWrong = solution && checked && mine === j && j !== q.key;
                const picked = !solution && mine === j;
                return (
                  <Pressable
                    key={j}
                    accessibilityRole="radio"
                    aria-checked={mine === j}
                    accessibilityLabel={`${LETTER[j]}. ${o}`}
                    disabled={solution || checked}
                    onPress={() => setChosen((cur) => cur.map((x, k) => (k === i ? j : x)))}
                    style={{
                      flexDirection: "row",
                      gap: Space.sm,
                      minHeight: 44,
                      alignItems: "center",
                      borderRadius: Radius.md,
                      borderWidth: picked ? 2 : 1,
                      borderColor: isKey ? c.ok : isWrong ? c.danger : picked ? c.accent : c.border,
                      backgroundColor: isKey ? c.okSoft : isWrong ? c.dangerSoft : picked ? c.accentSoft : "transparent",
                      paddingHorizontal: Space.md,
                      paddingVertical: Space.xs,
                    }}>
                    <Text style={{ fontWeight: "700", color: c.muted }}>{LETTER[j]}</Text>
                    <T style={{ flex: 1 }}>{o}</T>
                    {solution && checked && mine === j ? <Text style={{ fontSize: 12, fontWeight: "700", color: c.text }}>Your answer</Text> : null}
                  </Pressable>
                );
              })}
              {solution ? (
                <T variant="small">
                  <Text style={{ fontWeight: "700", color: c.ok }}>{`Correct answer: ${LETTER[q.key ?? 0]}`}</Text>
                  {verdict === "wrong" ? <Text style={{ color: c.danger }}>{` · you chose ${LETTER[mine ?? 0]}`}</Text> : null}
                  {q.answer.text ? <Text style={{ color: c.muted }}>{` — ${q.answer.text}`}</Text> : null}
                </T>
              ) : null}
            </View>
          );
        })}
        {!solution ? (
          <View style={{ alignItems: "center", gap: Space.sm, borderTopWidth: 1, borderColor: c.border, paddingTop: Space.md }}>
            <Button label="Submit MCQs" onPress={submit} disabled={checked} />
            <T variant="small" style={{ color: c.muted, textAlign: "center" }}>
              {checked ? "Submitted. Open the Solution paper to see your result." : "Submit when you have answered the MCQs."}
            </T>
          </View>
        ) : null}
      </Section>

      <Section label="Subjective">
        <Head head={head} kind="SUBJECTIVE" time={subjTime} marks={subjMarks} />
        {!solution ? timerBox(subjective.left, subjective.running, subjective.start, false) : null}
        <Text style={{ textAlign: "center", fontFamily: HeadingFont.bold, letterSpacing: 1, color: c.text, paddingTop: Space.sm }}>SECTION-I</Text>
        {paper.short.map((s) => (
          <View key={s.no}>
            <QHead title={`${s.no}. Write the answers of any ${WORDS[s.attempt] ?? s.attempt} parts.`} marks={`${s.attempt} × 2 = ${s.attempt * 2}`} />
            {s.parts.map((q, i) => (
              <Row key={i} label={`(${ROMAN[i]})`} q={q} solved={solution} />
            ))}
          </View>
        ))}
        <Text style={{ textAlign: "center", fontFamily: HeadingFont.bold, letterSpacing: 1, color: c.text, paddingTop: Space.md }}>SECTION-II</Text>
        <QHead
          title={`NOTE: Write answers of any ${WORDS[p.long.attempt] ?? p.long.attempt} questions.`}
          marks={`${p.long.attempt} × ${longTotal} = ${p.long.attempt * longTotal}`}
        />
        {paper.long.map((pr, i) => (
          <View key={i}>
            <Row label={pr.b ? `${i + 5}.(a)` : `${i + 5}.`} q={pr.a} marks={pr.a.marks} solved={solution} />
            {pr.b ? <Row label="(b)" q={pr.b} marks={pr.b.marks} solved={solution} /> : null}
          </View>
        ))}
      </Section>
    </View>
  );
}
