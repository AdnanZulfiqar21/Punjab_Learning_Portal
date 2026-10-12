// P08.S4.T3 (ITEM-STATS-01): how learners actually answered each published version of this question. Every figure
// shows its sample; below the minimum nothing is judged, and a flag is a prompt for a reviewer, never a verdict.
import type { ItemStats } from "@portal/contracts";
import { Badge } from "@/components/ui";

export const FLAG_TEXT: Record<string, string> = {
  very_hard: "Very few learners get it right: check the key and the wording.",
  very_easy: "Almost everyone gets it right: it may not tell learners apart.",
  weak_discrimination: "Strong and weak learners do about equally well on it: check for ambiguity.",
  distractor_beats_key: "A wrong option is chosen more often than the key: check the key.",
  unused_distractor: "A wrong option is never chosen: it may be implausible.",
};

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

export function QuestionStatistics({ stats }: { stats: ItemStats[] }) {
  return (
    <section aria-labelledby="question-stats-h" className="space-y-3 rounded-xl border border-border bg-surface px-4 py-3 text-sm">
      <h2 id="question-stats-h" className="font-semibold">
        How learners answered
      </h2>
      {stats.length === 0 ? (
        <p className="text-muted">No finished attempts have included this question yet.</p>
      ) : (
        stats.map((s) => (
          <div key={s.version} className="space-y-2 border-t border-border pt-2 first:border-t-0 first:pt-0">
            <p className="font-medium">
              Version {s.version}: {s.answered} answered, {s.blank} left blank
              {!s.enough && <span className="font-normal text-muted"> · too few responses to judge</span>}
            </p>
            <p>
              Correct: {pct(s.difficulty)} · discrimination {s.discrimination === null ? "not defined" : s.discrimination.toFixed(2)} (from {s.discrimination_sample})
            </p>
            <ul className="space-y-1" aria-label={`Option choices, version ${s.version}`}>
              {s.options.map((o) => (
                <li key={o.option_id} className="flex items-center gap-2">
                  <span className="w-10 font-mono text-xs">{o.option_id}</span>
                  <span className="h-2 rounded bg-accent/60" style={{ width: `${Math.round((o.rate ?? 0) * 160)}px` }} aria-hidden="true" />
                  <span>
                    {o.chosen} ({pct(o.rate)}){o.key ? " · key" : ""}
                  </span>
                </li>
              ))}
            </ul>
            {s.flags.length > 0 && (
              <ul className="space-y-1">
                {s.flags.map((f) => (
                  <li key={f}>
                    <Badge tone="warn">Worth a look</Badge> {FLAG_TEXT[f] ?? f}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))
      )}
      <p className="text-xs text-muted">Responses under a void or credit-all correction are left out. Nothing here changes the question.</p>
    </section>
  );
}
