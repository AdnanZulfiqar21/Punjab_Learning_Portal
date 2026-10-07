"use client";

import { useActionState } from "react";
import type { Profile } from "@portal/contracts";
import { saveProfile, type FormState } from "@/app/actions/auth";

const SUBJECTS: [string, string][] = [
  ["biology", "Biology"],
  ["chemistry", "Chemistry"],
  ["physics", "Physics"],
  ["computer_science", "Computer Science"],
  ["mathematics", "Mathematics"],
];
const STREAMS: [string, string][] = [
  ["pre_medical", "Pre-Medical"],
  ["pre_engineering", "Pre-Engineering"],
  ["ics", "ICS"],
];
const EXAMS: [string, string][] = [
  ["mdcat", "MDCAT"],
  ["ecat", "ECAT"],
];

const field = "w-full rounded-lg border border-border bg-surface px-3 py-2.5";

export function OnboardingForm({ profile }: { profile: Profile | null }) {
  const [state, action, pending] = useActionState<FormState, FormData>(saveProfile, undefined);
  return (
    <form action={action} className="space-y-6">
      <fieldset className="space-y-2">
        <legend className="font-medium">Which class are you in?</legend>
        <div className="flex gap-3">
          {[11, 12].map((g) => (
            <label key={g} className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5">
              <input type="radio" name="grade" value={g} defaultChecked={profile?.grade === g} required />
              Class {g === 11 ? "XI" : "XII"}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="space-y-1">
        <label htmlFor="stream" className="font-medium">
          Group
        </label>
        <select id="stream" name="stream" defaultValue={profile?.stream ?? ""} className={field}>
          <option value="">Not sure yet</option>
          {STREAMS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="space-y-2">
        <legend className="font-medium">Subjects</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {SUBJECTS.map(([v, l]) => (
            <label key={v} className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
              <input type="checkbox" name="subjects" value={v} defaultChecked={profile?.subjects?.includes(v as never)} />
              {l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="font-medium">Preparing for an entry test?</legend>
        <div className="flex flex-wrap gap-3">
          {EXAMS.map(([v, l]) => (
            <label key={v} className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2">
              <input type="checkbox" name="target_exams" value={v} defaultChecked={profile?.target_exams?.includes(v as never)} />
              {l}
            </label>
          ))}
        </div>
        <p className="text-sm text-muted">
          Full official-pattern mocks also need English (and Logical Reasoning for MDCAT), which are not part of this
          portal yet. Subject practice for your five subjects is available.
        </p>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1">
          <label htmlFor="target_year" className="font-medium">
            Test year
          </label>
          <input id="target_year" name="target_year" type="number" min={2026} max={2035} defaultValue={profile?.target_year ?? ""} className={field} />
        </div>
        <div className="space-y-1">
          <label htmlFor="explanation_language" className="font-medium">
            Explanations in
          </label>
          <select id="explanation_language" name="explanation_language" defaultValue={profile?.explanation_language ?? "en"} className={field}>
            <option value="en">English</option>
            <option value="ur">Urdu</option>
            <option value="roman_ur">Roman Urdu</option>
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="daily_minutes" className="font-medium">
            Minutes per day
          </label>
          <input id="daily_minutes" name="daily_minutes" type="number" min={10} max={600} step={5} defaultValue={profile?.daily_minutes ?? ""} className={field} />
        </div>
      </div>

      {state?.error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Saving…" : "Save and continue"}
      </button>
    </form>
  );
}
