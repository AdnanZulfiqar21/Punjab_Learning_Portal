"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { decideVoice, proposeVoice, startLecture, type LectureResult } from "@/app/actions/lectures";
import { LANGUAGE } from "./labels";

const field = "rounded-lg border border-border bg-surface px-3 py-2";
const button = "rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background";

/** Shows an action's error with the API's itemised reasons, if any. */
export function Problems({ result }: { result: LectureResult | null }) {
  if (!result || result.ok) return null;
  return (
    <div role="alert" className="w-full rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
      <p>{result.error}</p>
      {result.errors && result.errors.length > 0 && (
        <ul className="mt-1 list-disc pl-5">
          {result.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function useAction() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<LectureResult | null>(null);
  async function run(fn: () => Promise<LectureResult>, then?: (r: LectureResult) => void) {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    setResult(r);
    if (r.ok) {
      if (then) then(r);
      else router.refresh();
    }
  }
  return { busy, result, run, router };
}

export function ProposeVoice() {
  const { busy, result, run } = useAction();
  return (
    <details className="rounded-xl border border-border bg-surface p-4 text-sm">
      <summary className="cursor-pointer font-medium">Propose a narration voice</summary>
      <form action={(f) => run(() => proposeVoice(f))} className="mt-3 flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block">Name</span>
          <input name="name" required minLength={2} maxLength={120} className={field} />
        </label>
        <label className="space-y-1">
          <span className="block">Language</span>
          <select name="language" defaultValue="roman_ur" className={field}>
            {Object.entries(LANGUAGE).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="block">Production tool</span>
          <input name="tool" required minLength={2} maxLength={120} className={field} />
        </label>
        <label className="space-y-1">
          <span className="block">Tool&apos;s voice ID</span>
          <input name="voice_ref" required maxLength={200} className={field} />
        </label>
        <label className="w-full space-y-1">
          <span className="block">Notes (accent, pace, where the sample is)</span>
          <input name="notes" maxLength={2000} className={`${field} w-full`} />
        </label>
        <button type="submit" disabled={busy} className={button}>
          {busy ? "Proposing…" : "Propose"}
        </button>
        <Problems result={result} />
      </form>
    </details>
  );
}

export function VoiceDecision({ id, status }: { id: string; status: string }) {
  const { busy, result, run, router } = useAction();
  const [evidence, setEvidence] = useState("");
  const decide = (action: "approve" | "retire") =>
    run(
      () => decideVoice(id, action, evidence),
      () => {
        setEvidence("");
        router.refresh();
      },
    );
  return (
    <span className="flex w-full flex-wrap items-center gap-2">
      <input
        aria-label="Evidence for the decision"
        placeholder="Evidence (e.g. listened to the sample; chosen for Class XI Biology)"
        value={evidence}
        onChange={(e) => setEvidence(e.target.value)}
        className={`${field} min-w-60 flex-1 py-1`}
        maxLength={2000}
      />
      {status === "proposed" && (
        <button type="button" disabled={busy || evidence.trim().length < 10} onClick={() => decide("approve")} className={button}>
          Approve
        </button>
      )}
      <button
        type="button"
        disabled={busy || evidence.trim().length < 10}
        onClick={() => decide("retire")}
        className="rounded-lg border border-border px-4 py-2 font-medium hover:border-accent disabled:opacity-60"
      >
        Retire
      </button>
      <Problems result={result} />
    </span>
  );
}

export function StartLecture({
  storyboards,
  voices,
}: {
  storyboards: { id: string; title: string }[];
  voices: { id: string; name: string; language: string }[];
}) {
  const { busy, result, run, router } = useAction();
  const [language, setLanguage] = useState("roman_ur");
  const usable = voices.filter((v) => v.language === language);
  if (storyboards.length === 0) {
    return <p className="text-sm text-muted">A lecture starts from a reviewed, published storyboard. None is published in your scope yet.</p>;
  }
  return (
    <form
      action={(f) => run(() => startLecture(f), (r) => r.ok && r.id && router.push(`/studio/lectures/${r.id}`))}
      className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-surface p-4 text-sm"
    >
      <label className="space-y-1">
        <span className="block font-medium">Storyboard</span>
        <select name="storyboard_item_id" required className={field}>
          {storyboards.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Narration language</span>
        <select name="narration_language" value={language} onChange={(e) => setLanguage(e.target.value)} className={field}>
          {Object.entries(LANGUAGE).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1">
        <span className="block font-medium">Approved voice</span>
        <select name="voice_id" required className={field}>
          {usable.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={busy || usable.length === 0} className={button}>
        {busy ? "Starting…" : "Start lecture"}
      </button>
      {usable.length === 0 && <p className="w-full text-muted">No approved voice narrates {LANGUAGE[language]} yet.</p>}
      <Problems result={result} />
    </form>
  );
}
