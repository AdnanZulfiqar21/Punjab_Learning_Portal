"use client";

import { useActionState, useState } from "react";
import type { AdjudicationSources } from "@portal/contracts";
import { createAdjudication, type AdjudicationFormState } from "@/app/actions/adjudication";

type Version = { id: string; number: number; denominator_compatible: boolean; compatibility: { carry_forward: boolean; criteria: Record<string, string> }; claimed_by: string[]; submitted_scripts: number };

// W06-07: the adjudicator chooses exactly which earlier versions this correction covers and which active corrections
// it replaces; the chain, compatibility, denominator check and affected scripts are shown before anything is committed.
export function NewAdjudicationForm({ rubricId, sources }: { rubricId: string; sources: AdjudicationSources }) {
  const [state, action, pending] = useActionState<AdjudicationFormState, FormData>(createAdjudication, undefined);
  const versions = sources.versions as unknown as Version[];
  const [chosen, setChosen] = useState<string[]>(versions.filter((v) => v.denominator_compatible).map((v) => v.id));
  const overlapping = [...new Set(versions.filter((v) => chosen.includes(v.id)).flatMap((v) => v.claimed_by))];
  const scripts = versions.filter((v) => chosen.includes(v.id)).reduce((n, v) => n + v.submitted_scripts, 0);
  return (
    <form action={action} className="space-y-4">
      <input type="hidden" name="rubric_item_id" value={rubricId} />
      <fieldset className="space-y-2">
        <legend className="font-medium">Earlier versions this correction covers</legend>
        {versions.map((v) => {
          const changed = Object.entries(v.compatibility.criteria).filter(([, k]) => k !== "unchanged");
          return (
            <label key={v.id} className="flex items-start gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
              <input
                type="checkbox"
                name="from_version_ids"
                value={v.id}
                checked={chosen.includes(v.id)}
                disabled={!v.denominator_compatible}
                onChange={(e) => setChosen((c) => (e.target.checked ? [...c, v.id] : c.filter((x) => x !== v.id)))}
              />
              <span>
                <span className="font-medium">Version {v.number}</span> → version {sources.published_number} ·{" "}
                {!v.denominator_compatible
                  ? "different maxima: not a rubric correction"
                  : v.compatibility.carry_forward
                    ? "scoring basis identical — marks carry forward"
                    : `scoring changed (${changed.map(([c, k]) => `${c} ${k}`).join(", ")}) — teachers re-mark`}{" "}
                · {v.submitted_scripts} submitted script(s)
                {v.claimed_by.length > 0 && <span className="block text-muted">Already covered by an active correction</span>}
              </span>
            </label>
          );
        })}
      </fieldset>
      {overlapping.length > 0 && (
        <fieldset className="space-y-1 rounded-lg border border-warn bg-warn-soft p-3 text-sm">
          <legend className="font-medium">Active corrections this one replaces</legend>
          <p>These versions are already covered. Tick each correction you are replacing; it stops applying and this one is applied instead.</p>
          {overlapping.map((id) => (
            <label key={id} className="flex items-center gap-2">
              <input type="checkbox" name="supersedes_ids" value={id} />
              Replace correction {id.slice(0, 8)}
            </label>
          ))}
        </fieldset>
      )}
      <p className="text-sm text-muted" role="status">
        {chosen.length} version(s) selected · up to {scripts} submitted script(s) affected
      </p>
      <label className="block space-y-1">
        <span className="font-medium">Why does this correction apply to work already marked?</span>
        <textarea name="reason" required minLength={20} maxLength={2000} rows={4} className="w-full rounded-lg border border-border bg-surface px-3 py-2" />
      </label>
      {state?.error && (
        <p role="alert" className="text-sm text-danger">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending || chosen.length === 0}
        className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
      >
        {pending ? "Approving…" : "Approve the correction"}
      </button>
    </form>
  );
}
