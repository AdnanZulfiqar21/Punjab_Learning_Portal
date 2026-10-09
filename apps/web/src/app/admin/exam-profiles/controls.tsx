"use client";

import { useState, useTransition } from "react";
import { createProfile, publishVersion, saveDraft, verifyVersion } from "@/app/actions/exam-profiles";

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const btn = "rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-accent disabled:opacity-60";

export const RULES_TEMPLATE = JSON.stringify(
  {
    source_url: "https://…",
    source_note: "What was read, where and when",
    duration_minutes: 0,
    late_write_tolerance_ms: 0,
    marks_per_question: 1,
    negative_marks: 0,
    invalid_item_treatment: "EXCLUDE",
    solution_release: "after_submission",
    sections: [{ subject: "biology", grades: [11, 12], questions: 0, label: "" }],
  },
  null,
  2,
);

function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const run = (fn: () => Promise<{ ok: boolean; error?: string }>, onOk?: () => void) =>
    start(async () => {
      setError(null);
      const out = await fn();
      if (out.ok) onOk?.();
      else setError(out.error ?? "Something went wrong.");
    });
  const alert = error ? (
    <p role="alert" className="text-sm text-danger">
      {error}
    </p>
  ) : null;
  return { pending, run, alert };
}

export function NewProfile() {
  const [v, setV] = useState({ code: "", name: "", note: "" });
  const { pending, run, alert } = useAction();
  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface p-4">
      <h2 className="font-semibold">New exam profile</h2>
      <input aria-label="Profile code" placeholder="Code, e.g. MDCAT" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} className={field} />
      <input aria-label="Profile name" placeholder="Name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} className={field} />
      <textarea aria-label="Eligibility note" placeholder="Eligibility guidance with its source (taking this test doesn't guarantee admission)" value={v.note} onChange={(e) => setV({ ...v, note: e.target.value })} rows={2} className={field} />
      <button type="button" className={btn} disabled={pending || v.code.trim().length < 2 || v.name.trim().length < 3} onClick={() => run(() => createProfile(v.code.trim(), v.name.trim(), v.note.trim()), () => setV({ code: "", name: "", note: "" }))}>
        Create profile
      </button>
      {alert}
    </div>
  );
}

export function DraftEditor({ profileId, versionId, initialYear, initialRules }: { profileId: string; versionId: string | null; initialYear: number; initialRules: string }) {
  const [year, setYear] = useState(initialYear);
  const [rules, setRules] = useState(initialRules);
  const { pending, run, alert } = useAction();
  return (
    <div className="space-y-2">
      <label className="block text-sm">
        <span className="font-medium">Year</span>
        <input type="number" min={2020} max={2100} value={year} onChange={(e) => setYear(Number(e.target.value))} className={`${field} w-32`} />
      </label>
      <label className="block text-sm">
        <span className="font-medium">Rules (JSON: source, duration, marking, correction policy, sections)</span>
        <textarea value={rules} onChange={(e) => setRules(e.target.value)} rows={14} spellCheck={false} className={`${field} font-mono`} />
      </label>
      <button type="button" className={btn} disabled={pending} onClick={() => run(() => saveDraft(profileId, versionId, year, rules))}>
        {versionId ? "Save draft (clears verifications)" : "Start a new draft version"}
      </button>
      {alert}
    </div>
  );
}

export function VerifyPublish({ versionId, status }: { versionId: string; status: string }) {
  const [note, setNote] = useState("");
  const { pending, run, alert } = useAction();
  return (
    <div className="space-y-2">
      {status === "draft" && (
        <>
          <label className="block text-sm">
            <span className="font-medium">Verification note (what you checked against the official source)</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className={field} />
          </label>
          <button type="button" className={btn} disabled={pending || note.trim().length < 10} onClick={() => run(() => verifyVersion(versionId, note.trim()), () => setNote(""))}>
            Record my verification
          </button>
        </>
      )}
      {status === "verified" && (
        <button type="button" className={btn} disabled={pending} onClick={() => run(() => publishVersion(versionId))}>
          Publish this version
        </button>
      )}
      {alert}
    </div>
  );
}
