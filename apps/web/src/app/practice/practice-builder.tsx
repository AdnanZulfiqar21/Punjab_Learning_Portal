"use client";

import { useActionState, useRef, useState } from "react";
import type { PracticeAvailability } from "@portal/contracts";
import { createPractice, type BuilderState } from "@/app/actions/practice";

const newKey = () => crypto.randomUUID().replaceAll("-", "");

export function PracticeBuilder({
  grade,
  subject,
  chapters,
  subjects,
  secondsPerQuestion = null,
  estimateBasedOn = 0,
}: {
  grade: number;
  subject: string;
  chapters: PracticeAvailability["chapters"];
  subjects: [string, string][];
  secondsPerQuestion?: number | null;
  estimateBasedOn?: number;
}) {
  // One idempotency key per test request: a double click or a retry returns the same test; a changed request gets a
  // fresh key after an error so it is never mistaken for the earlier one.
  const key = useRef<string | null>(null);
  const [state, action, pending] = useActionState<BuilderState, FormData>(async (prev, form) => {
    key.current ??= newKey();
    form.set("idempotency_key", key.current);
    const out = await createPractice(prev, form);
    if (out?.error) key.current = null;
    return out;
  }, undefined);
  const [selected, setSelected] = useState<string[]>([]);
  // P11.S3.T1 (PRACTICE-CONFIG-01): optional topics inside the chosen chapters. Choosing any limits the whole test to
  // the chosen topics, as the API does.
  const [topics, setTopics] = useState<string[]>([]);
  const [timed, setTimed] = useState(false);
  // P09.S1.T2: halves follow the book's chapter order (first half = the first ceil(n/2) chapters).
  const [scope, setScope] = useState<"chapters" | "half_1" | "half_2" | "full_book" | "combined" | "multi_subject">("chapters");
  // P09.S1.T3: a custom mix of this class's subjects, each with its own count (0 leaves a subject out).
  const [mix, setMix] = useState<Record<string, number>>({ [subject]: 5 });
  const mixTotal = Object.values(mix).reduce((n, v) => n + v, 0);
  const mixSubjects = Object.values(mix).filter((v) => v > 0).length;
  const split = Math.ceil(chapters.length / 2);
  const inScope =
    scope === "chapters" ? chapters.filter((c) => selected.includes(c.chapter_id)) : scope === "half_1" ? chapters.slice(0, split) : scope === "half_2" ? chapters.slice(split) : chapters;
  // The other class's book isn't listed here, so a combined test can ask for more than this book alone holds.
  const chosenTopics = scope === "chapters" ? inScope.flatMap((c) => (c.topics ?? []).filter((t) => topics.includes(t.topic_id))) : [];
  const available =
    scope === "combined" || scope === "multi_subject"
      ? 100
      : chosenTopics.length
        ? chosenTopics.reduce((n, t) => n + t.questions, 0)
        : inScope.reduce((n, c) => n + c.questions, 0);
  const [countText, setCountText] = useState("10");
  const asked = scope === "multi_subject" ? mixTotal : Math.max(1, Math.min(Number(countText) || 1, Math.max(1, available)));
  // A measured median, never a guess (PRACTICE-CONFIG-01); rounded up to whole minutes.
  const estimate = secondsPerQuestion ? Math.max(1, Math.ceil((asked * secondsPerQuestion) / 60)) : null;
  const ready = scope === "chapters" ? selected.length > 0 : scope === "multi_subject" ? mixSubjects >= 2 && mixTotal <= 100 : true;
  const field = "rounded-lg border border-border bg-surface px-3 py-2";

  return (
    <form action={action} className="space-y-6">
      <input type="hidden" name="grade" value={grade} />
      <input type="hidden" name="subject" value={subject} />
      <input type="hidden" name="scope" value={scope.startsWith("half") ? "half_book" : scope} />
      {scope.startsWith("half") && <input type="hidden" name="half" value={scope === "half_1" ? "1" : "2"} />}
      <fieldset className="space-y-2">
        <legend className="font-medium">What to cover</legend>
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["chapters", "Chosen chapters"],
              ["half_1", "First half of the book"],
              ["half_2", "Second half of the book"],
              ["full_book", "Whole book"],
              ["combined", "Class XI and XII together"],
              ["multi_subject", "Several subjects (custom mix)"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
              <input type="radio" name="scope_choice" value={value} checked={scope === value} onChange={() => setScope(value)} /> {label}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-2" hidden={scope !== "chapters"}>
        <legend className="font-medium">Chapters</legend>
        <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
          {chapters.map((c) => (
            <li key={c.chapter_id}>
              <label className={`flex items-center gap-3 px-4 py-3 ${c.questions === 0 ? "text-muted" : ""}`}>
                <input
                  type="checkbox"
                  name="chapter_ids"
                  value={c.chapter_id}
                  disabled={c.questions === 0}
                  checked={selected.includes(c.chapter_id)}
                  onChange={(e) => {
                    setSelected(e.target.checked ? [...selected, c.chapter_id] : selected.filter((x) => x !== c.chapter_id));
                    if (!e.target.checked) setTopics((ts) => ts.filter((t) => !(c.topics ?? []).some((x) => x.topic_id === t)));
                  }}
                />
                <span className="flex-1">
                  Chapter {c.number}: {c.title}
                </span>
                <span className="text-sm text-muted">{c.questions === 0 ? "no questions yet" : `${c.questions} question${c.questions === 1 ? "" : "s"}`}</span>
              </label>
              {selected.includes(c.chapter_id) && (c.topics ?? []).length > 0 && (
                <fieldset className="space-y-1 px-4 pb-3 pl-11 text-sm">
                  <legend className="sr-only">Topics in chapter {c.number}</legend>
                  <p className="text-muted">Only some topics? (optional; choosing any limits the whole test to the topics you choose)</p>
                  {(c.topics ?? []).map((t) => (
                    <label key={t.topic_id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        name="topic_ids"
                        value={t.topic_id}
                        checked={topics.includes(t.topic_id)}
                        onChange={(e) => setTopics(e.target.checked ? [...topics, t.topic_id] : topics.filter((x) => x !== t.topic_id))}
                      />
                      <span className="flex-1">
                        {t.number ? `${t.number} ` : ""}
                        {t.title}
                      </span>
                      <span className="text-muted">
                        {t.questions} question{t.questions === 1 ? "" : "s"}
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
            </li>
          ))}
        </ul>
      </fieldset>
      <fieldset className="space-y-2" hidden={scope !== "multi_subject"}>
        <legend className="font-medium">Questions per subject</legend>
        <p className="text-sm text-muted">
          Custom practice from each subject&apos;s whole book in this class. It isn&apos;t an official test pattern; for those, use
          a mock test. Choose two to five subjects.
        </p>
        <div className="flex flex-wrap gap-3">
          {subjects.map(([code, name]) => (
            <label key={code} className="space-y-1">
              <span className="block text-sm">{name}</span>
              <input
                type="number"
                name={`mix_${code}`}
                min={0}
                max={100}
                value={mix[code] ?? 0}
                onChange={(e) => setMix({ ...mix, [code]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) })}
                className={`${field} w-24`}
              />
            </label>
          ))}
        </div>
        <p className="text-sm text-muted" aria-live="polite">
          {mixTotal} questions from {mixSubjects} subject{mixSubjects === 1 ? "" : "s"}
          {mixTotal > 100 ? " (at most 100 in one test)" : ""}.
        </p>
      </fieldset>
      <div className="flex flex-wrap items-end gap-4">
        <label className="space-y-1" hidden={scope === "multi_subject"}>
          <span className="block font-medium">Questions</span>
          <input
            type="number"
            name="question_count"
            min={1}
            max={Math.max(1, Math.min(100, available))}
            value={countText}
            onChange={(e) => setCountText(e.target.value)}
            className={`${field} w-28`}
          />
        </label>
        <label className="space-y-1">
          <span className="block font-medium">Feedback</span>
          <select name="feedback_mode" defaultValue="deferred" className={field}>
            <option value="deferred">After I submit</option>
            <option value="immediate">After each question</option>
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2">
          <input type="checkbox" name="timed" checked={timed} onChange={(e) => setTimed(e.target.checked)} />
          Timed
        </label>
        {timed && (
          <label className="space-y-1">
            <span className="block font-medium">Minutes</span>
            <input type="number" name="timed_minutes" min={1} max={300} defaultValue={15} className={`${field} w-24`} />
          </label>
        )}
      </div>
      {timed && (
        <p className="text-sm text-muted">
          Timed practice closes editing at the deadline. Answers that haven&apos;t reached the server within 3 seconds after it can be
          rejected, so keep your connection steady near the end.
        </p>
      )}
      {selected.length > 0 && (
        <p className="text-sm text-muted">
          {available} approved question{available === 1 ? "" : "s"} available in the chosen {chosenTopics.length ? "topics" : "chapters"}.
        </p>
      )}
      <p className="text-sm text-muted" aria-live="polite">
        {estimate !== null
          ? `About ${estimate} minute${estimate === 1 ? "" : "s"} for ${asked} question${asked === 1 ? "" : "s"}, measured from how long learners took in ${estimateBasedOn} submitted tests here.`
          : "No time estimate yet: not enough submitted tests in this subject to measure one."}
      </p>
      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
          {state.available !== undefined ? ` You can ask for up to ${state.available}.` : ""}
        </p>
      )}
      <button
        type="submit"
        disabled={pending || !ready}
        className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Preparing…" : "Start test"}
      </button>
    </form>
  );
}
