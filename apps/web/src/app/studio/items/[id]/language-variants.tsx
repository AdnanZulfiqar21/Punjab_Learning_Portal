"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import type { LessonVariant } from "@portal/contracts";
import { createLanguageVariant } from "@/app/actions/studio";
import { Badge } from "@/components/ui";

export const LANGUAGE_LABEL: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };
const STATE: Record<string, string> = {
  draft: "Draft",
  submitted: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  published: "Published",
};

/** P07.S1.T2: a lesson concept's language versions, each with its own review status, and adding a missing one. */
export function LanguageVariants({ itemId, title, variants, canAdd }: { itemId: string; title: string; variants: LessonVariant[]; canAdd: boolean }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const missing = Object.keys(LANGUAGE_LABEL).filter((l) => !variants.some((v) => v.language === l && v.availability !== "retired"));
  const [language, setLanguage] = useState(missing[0] ?? "");
  const [origin, setOrigin] = useState("human");
  return (
    <section aria-labelledby="variants-h" className="space-y-2 rounded-xl border border-border bg-surface px-4 py-3 text-sm">
      <h2 id="variants-h" className="font-semibold">
        Language versions
      </h2>
      <ul className="space-y-1">
        {variants.map((v) => (
          <li key={v.item_id} className="flex flex-wrap items-center gap-2">
            <Badge tone={v.state === "published" && v.availability === "live" ? "ok" : "info"}>{STATE[v.state] ?? v.state}</Badge>
            {v.item_id === itemId ? (
              <span className="font-medium">{LANGUAGE_LABEL[v.language]} (this item)</span>
            ) : (
              <Link href={`/studio/items/${v.item_id}`} className="text-accent underline-offset-2 hover:underline">
                {LANGUAGE_LABEL[v.language]}
              </Link>
            )}
            {v.original && <span className="text-muted">original</span>}
            {v.translation_origin === "machine_draft" && <span className="text-muted">machine draft: check every sentence against the original</span>}
          </li>
        ))}
      </ul>
      {canAdd && missing.length > 0 && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="space-y-1">
            <span className="block">Add a version in</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded-lg border border-border bg-surface px-2 py-1.5">
              {missing.map((l) => (
                <option key={l} value={l}>
                  {LANGUAGE_LABEL[l]}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="block">Translated by</span>
            <select value={origin} onChange={(e) => setOrigin(e.target.value)} className="rounded-lg border border-border bg-surface px-2 py-1.5">
              <option value="human">A person</option>
              <option value="machine_draft">A machine (draft for review)</option>
            </select>
          </label>
          <button
            type="button"
            disabled={pending || !language}
            onClick={() =>
              start(async () => {
                const out = await createLanguageVariant(itemId, `${title} (${LANGUAGE_LABEL[language]})`, language, origin);
                if (out?.error) setError(out.error);
              })
            }
            className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium hover:border-accent disabled:opacity-60"
          >
            {pending ? "Creating…" : "Start this version"}
          </button>
        </div>
      )}
      <p className="text-xs text-muted">Each version is reviewed and published on its own. Learners who choose a language without a published version are told so and shown another.</p>
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
