"use client";

// Teacher marking workspace (W06.S1): evidence beside the pinned question and rubric. Awards are limited to the
// rubric's permitted levels; the API re-checks levels, unanswered parts, dependencies, alternative routes, the lease and
// the expected version, so a stale or conflicting decision is reported, never silently applied.
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { MarkingCase } from "@portal/contracts";
import { rebaseRecheck, saveMarks, takeLease } from "@/app/actions/marking";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Notice } from "@/components/ui";

type Criterion = { id: string; subpart_id: string | null; description: string; max_units: number; levels: number[]; alternative_group?: string | null };
type Rubric = { criteria: Criterion[]; expected_concepts?: string[]; consequential_error_rule?: string; units_rule?: string; crossed_out_rule?: string };
type Question = { stem: { type: string }[]; subparts: { id: string; label: string; blocks: { type: string }[]; max_units: number }[] };
type Awards = Record<string, Record<string, { units: number; reason: string }>>;
const marks = (u: number) => String(u / 100);

// RS31-03 / PR32-04: the API's authoritative timing; sent after submission is not necessarily after the upload deadline.
const TIMING: Record<string, string> = {
  before_cutoff: "before the upload deadline",
  at_cutoff: "at the upload deadline (within the window)",
  after_cutoff: "after the upload deadline",
};

const KIND_LABEL: Record<string, string> = {
  initial: "First marking",
  recheck: "Recheck",
  completion: "Completion",
  regrade: "Regrade after a rubric correction",
};

export function MarkingWorkspace({ initial }: { initial: MarkingCase }) {
  const router = useRouter();
  const [c, setC] = useState(initial);
  const [pending, start] = useTransition();
  const [error, setError] = useState<{ text: string; list?: string[]; conflict?: boolean; code?: string } | null>(null);
  const [rebaseReason, setRebaseReason] = useState("");
  const [awards, setAwards] = useState<Awards>(() => {
    const prior = (c.latest?.awards ?? {}) as Awards;
    const out: Awards = {};
    for (const q of c.questions) {
      const r = q.rubric as unknown as Rubric;
      out[String(q.position)] = Object.fromEntries(
        r.criteria.map((cr) => [cr.id, { units: prior[String(q.position)]?.[cr.id]?.units ?? 0, reason: prior[String(q.position)]?.[cr.id]?.reason ?? "" }]),
      );
    }
    return out;
  });
  // A recheck re-marks only the learner's questions (plus any an adjudicator adds with a reason); the rest carry forward.
  const rc = c.recheck;
  const cp = c.completion;
  const rg = c.regrade; // W06.S2.T3: questions a rubric correction changed
  const [added, setAdded] = useState<number[]>([]);
  const [expansionReason, setExpansionReason] = useState("");
  // R05: each question in scope is scored, pending (e.g. unreadable) or unavailable (can't be assessed).
  // PR32-02: a saved draft reopens with everything it intended, not just its awards.
  const [status, setStatus] = useState<Record<string, { status: "scored" | "pending" | "unavailable"; reason: string; learner_action?: string }>>(
    () => (initial.draft?.question_status ?? {}) as Record<string, { status: "scored" | "pending" | "unavailable"; reason: string; learner_action?: string }>,
  );
  const [classes, setClasses] = useState<Record<string, { class: string; reason: string }>>(
    () => (initial.draft?.classifications ?? {}) as Record<string, { class: string; reason: string }>,
  );
  // Section 4 (PR #31 review): which READABILITY copies supplied each marked answer; none means the sealed original.
  const [used, setUsed] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(Object.values(initial.draft?.evidence ?? {}).flatMap((ids) => ids.map((id) => [id, true]))),
  );
  const readable = (r: { id: string; classification?: string | null }) => (r.classification ?? classes[r.id]?.class) === "READABILITY";
  const evidence = () => {
    const out: Record<string, string[]> = {};
    for (const r of c.revisions) if (used[r.id] && readable(r)) (out[String(r.position)] ??= []).push(r.id);
    return out;
  };
  const statusOf = (pos: string) => status[pos]?.status ?? "scored";
  const carried = rc?.carried_forward ?? cp?.carried_forward ?? rg?.carried_forward ?? {};
  const scope = rc
    ? new Set([...rc.positions, ...rc.expanded_positions, ...added].map(String))
    : cp
      ? new Set(cp.positions.map(String))
      : rg
        ? new Set(rg.positions.map(String))
      : null;
  const inScope = (pos: string) => !scope || scope.has(pos);
  const slots = (c.manifest as { slots?: Record<string, { pages?: string[]; unanswered?: boolean }> }).slots ?? {};
  const pageNo = (id: string) => c.pages.findIndex((p) => p.id === id) + 1;
  const total = Object.entries(awards).reduce(
    (n, [pos, q]) =>
      n + (inScope(pos) ? (statusOf(pos) === "scored" ? Object.values(q).reduce((m, a) => m + a.units, 0) : 0) : (carried[pos] ?? 0)),
    0,
  );
  const sent = () => Object.fromEntries(Object.entries(awards).filter(([pos]) => inScope(pos) && statusOf(pos) === "scored"));
  const sentStatus = () => Object.fromEntries(Object.entries(status).filter(([pos, st]) => inScope(pos) && st.status !== "scored"));
  const expansion = () => (added.length ? { positions: added, reason: expansionReason.trim() } : undefined);
  const canMark = c.leased_by_me && c.status === "queued";

  function set(pos: string, id: string, patch: Partial<{ units: number; reason: string }>) {
    setAwards((a) => ({ ...a, [pos]: { ...a[pos], [id]: { ...a[pos][id], ...patch } } }));
  }

  function run(fn: () => ReturnType<typeof takeLease>) {
    setError(null);
    start(async () => {
      const out = await fn();
      if (out.ok) {
        setC(out.case);
        router.refresh();
      } else setError({ text: out.error, list: out.errors, conflict: out.conflict, code: out.code });
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Script {c.reference}</h1>
          <p className="text-sm text-muted">
            {KIND_LABEL[c.case_kind] ?? c.case_kind} · out of {marks(c.max_units)} marks · version {c.version}
          </p>
        </div>
        <div className="flex gap-2">
          {c.status === "released" && <Badge tone="ok">Result released</Badge>}
          {c.leased_by_other && <Badge tone="warn">Another teacher is marking</Badge>}
          {c.status === "queued" && !c.leased_by_me && (
            <button type="button" disabled={pending || c.leased_by_other} onClick={() => run(() => takeLease(c.id))} className="rounded-lg bg-accent px-4 py-2 font-medium text-white disabled:opacity-60 dark:text-background">
              Start marking
            </button>
          )}
        </div>
      </header>
      {error && (
        <div role="alert" className="space-y-1 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          <p>{error.text}</p>
          {error.list && (
            <ul className="list-disc pl-5">
              {error.list.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
          {error.conflict && (
            <button type="button" className="underline" onClick={() => router.refresh()}>
              Reload the latest version
            </button>
          )}
          {error.code === "RECHECK_TARGET_CHANGED" && c.recheck?.can_expand && (
            <div className="space-y-1 pt-2">
              <label htmlFor="rebase-reason" className="font-medium">
                Rebase this recheck onto the current result (reason recorded)
              </label>
              <textarea id="rebase-reason" value={rebaseReason} onChange={(e) => setRebaseReason(e.target.value)} rows={2} maxLength={1000} className="w-full rounded border border-border bg-surface px-2 py-1" />
              <button type="button" disabled={pending || rebaseReason.trim().length < 10} onClick={() => run(() => rebaseRecheck(c.id, rebaseReason.trim()))} className="rounded-lg border border-border bg-surface px-3 py-1.5 disabled:opacity-60">
                Rebase recheck
              </button>
            </div>
          )}
        </div>
      )}

      {rc && (
        <section aria-label="Recheck request" className="space-y-1 rounded-xl border border-warn bg-warn-soft p-4 text-sm">
          <p className="font-semibold">
            The learner disputes version {rc.target_version}: question{rc.positions.length > 1 ? "s" : ""} {rc.positions.join(", ")}
          </p>
          <p className="whitespace-pre-line">{rc.reason}</p>
          {rc.expanded_positions.length > 0 && <p>Added by an adjudicator: question {rc.expanded_positions.join(", ")}</p>}
          <p className="text-muted">Re-mark only these questions. Every other question keeps its released marks.</p>
        </section>
      )}
      {rg && (
        <section aria-label="Rubric correction" className="space-y-1 rounded-xl border border-warn bg-warn-soft p-4 text-sm">
          <p className="font-semibold">Re-mark question{rg.positions.length > 1 ? "s" : ""} {rg.positions.join(", ")} under the corrected rubric</p>
          <p className="whitespace-pre-line">{rg.reason}</p>
          <p className="text-muted">The rubric shown is the corrected one. Every other question keeps its released marks.</p>
        </section>
      )}
      {cp && (
        <section aria-label="Pending questions" className="space-y-1 rounded-xl border border-warn bg-warn-soft p-4 text-sm">
          <p className="font-semibold">Complete the pending question{cp.positions.length > 1 ? "s" : ""}: {cp.positions.join(", ")}</p>
          <p className="whitespace-pre-line">{cp.reason}</p>
          <p className="text-muted">Questions already released keep their marks.</p>
        </section>
      )}

      {c.revisions.length > 0 && (
        <section aria-label="Clearer copies from the learner" className="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm">
          <h2 className="font-semibold">Clearer copies (compare with the original pages)</h2>
          {c.revisions.map((r) => (
            <div key={r.id} className="space-y-2 border-t border-border pt-2">
              <p>
                Question {r.position} · sent {new Date(r.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })} · {TIMING[r.cutoff_timing]}
                {r.note ? ` · “${r.note}”` : ""}
              </p>
              <div className="flex flex-wrap gap-2">
                {r.pages.map((p, i) => (
                  // eslint-disable-next-line @next/next/no-img-element -- private evidence served by our own route
                  <img key={p.id} src={`/studio/marking/${c.id}/pages/${p.id}`} alt={`Clearer copy ${i + 1} for question ${r.position}`} className="h-48 rounded border border-border" />
                ))}
              </div>
              {r.classification ? (
                <p className="text-muted">
                  Classified {r.classification}: {r.class_reason}
                </p>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    aria-label={`Classify the clearer copy for question ${r.position}`}
                    value={classes[r.id]?.class ?? ""}
                    disabled={!canMark}
                    onChange={(e) => setClasses((all) => ({ ...all, [r.id]: { class: e.target.value, reason: all[r.id]?.reason ?? "" } }))}
                    className="rounded border border-border bg-surface px-2 py-1"
                  >
                    <option value="">Choose…</option>
                    <option value="READABILITY">Same answer, easier to read</option>
                    <option value="NEW_CONTENT">New or changed work</option>
                    <option value="INDETERMINATE">Can&apos;t tell (original too unclear)</option>
                  </select>
                  <input
                    aria-label={`Reason for the classification of question ${r.position}`}
                    placeholder="Reason (recorded)"
                    value={classes[r.id]?.reason ?? ""}
                    disabled={!canMark}
                    onChange={(e) => setClasses((all) => ({ ...all, [r.id]: { class: all[r.id]?.class ?? "", reason: e.target.value } }))}
                    className="min-w-60 flex-1 rounded border border-border bg-surface px-2 py-1"
                    maxLength={1000}
                  />
                </div>
              )}
            </div>
          ))}
          {c.revisions.some(readable) && (
            <fieldset className="space-y-1">
              <legend className="font-medium">Which copies did you use to mark?</legend>
              {c.revisions.filter(readable).map((r) => (
                <label key={r.id} className="flex items-center gap-2">
                  <input type="checkbox" checked={!!used[r.id]} disabled={!canMark} onChange={(e) => setUsed((u) => ({ ...u, [r.id]: e.target.checked }))} />
                  Used the clearer copy for question {r.position} (recorded with the mark)
                </label>
              ))}
            </fieldset>
          )}
          <p className="text-muted">Only a copy you classify as the same answer may be used to mark it. Nothing is classified automatically.</p>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-label="Submitted pages" className="space-y-3">
          {c.pages.map((p, i) => (
            <figure key={p.id} className="rounded-lg border border-border bg-surface p-2">
              {/* eslint-disable-next-line @next/next/no-img-element -- validated private preview served by our own route */}
              <img src={`/studio/marking/${c.id}/pages/${p.id}`} alt={`Submitted page ${i + 1}`} className="w-full rounded" />
              <figcaption className="mt-1 space-y-1 text-sm text-muted">
                <span>
                  Page {i + 1}
                  {p.file_pages > 1 && ` · PDF page ${p.page_index} of ${p.file_pages}`} ·{" "}
                  <a href={`/studio/marking/${c.id}/pages/${p.id}/detail`} target="_blank" rel="noreferrer" className="text-accent underline">
                    Open in full detail
                  </a>
                </span>
                {/* Higher-detail regions rendered from the original: small symbols, subscripts and labels (OCT8-06). */}
                <span className="grid w-28 grid-cols-3 gap-0.5" aria-label={`Zoom into part of page ${i + 1}`}>
                  {[0, 1, 2].flatMap((row) =>
                    [0, 1, 2].map((col) => (
                      <a
                        key={`${row}-${col}`}
                        href={`/studio/marking/${c.id}/pages/${p.id}/detail?region=${(col / 3).toFixed(4)},${(row / 3).toFixed(4)},0.3333,0.3333`}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Zoom: row ${row + 1}, column ${col + 1}`}
                        className="block h-6 rounded border border-border bg-surface hover:border-accent"
                      />
                    )),
                  )}
                </span>
              </figcaption>
            </figure>
          ))}
        </section>

        <section aria-label="Marks" className="space-y-4">
          {c.questions.map((q) => {
            const pos = String(q.position);
            const r = q.rubric as unknown as Rubric;
            const body = q.question as unknown as Question;
            const qTotal = Object.values(awards[pos] ?? {}).reduce((n, a) => n + a.units, 0);
            if (!inScope(pos)) {
              return (
                <article key={pos} aria-label={`Question ${pos}, carried forward`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface-muted p-4">
                  <div>
                    <h2 className="font-semibold">Question {pos}</h2>
                    <p className="text-sm text-muted">
                      Carried forward unchanged: {pos in carried ? `${marks(carried[pos])} / ${marks(q.max_units)}` : "not scored"}
                    </p>
                  </div>
                  {rc?.can_expand && canMark && (
                    <button type="button" onClick={() => setAdded((a) => [...a, q.position].sort((x, y) => x - y))} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm hover:border-accent">
                      Add to recheck
                    </button>
                  )}
                </article>
              );
            }
            const disputed = new Set(rc?.criteria[pos] ?? []);
            return (
              <article key={pos} className="space-y-3 rounded-xl border border-border bg-surface p-4">
                <div className="flex justify-between">
                  <h2 className="font-semibold">Question {pos}</h2>
                  <span className="text-sm">
                    {marks(qTotal)} / {marks(q.max_units)}
                  </span>
                </div>
                <LessonBlocks blocks={body.stem} headingOffset={2} />
                {c.case_kind !== "recheck" && c.case_kind !== "regrade" && (
                  <div className="flex flex-wrap items-center gap-3 rounded-lg bg-surface-muted p-2 text-sm">
                    <label className="flex items-center gap-2">
                      Outcome
                      <select
                        aria-label={`Outcome for question ${pos}`}
                        value={statusOf(pos)}
                        disabled={!canMark}
                        onChange={(e) => setStatus((s) => ({ ...s, [pos]: { status: e.target.value as "scored", reason: s[pos]?.reason ?? "" } }))}
                        className="rounded border border-border bg-surface px-2 py-1"
                      >
                        <option value="scored">Mark it</option>
                        <option value="pending">Pending (e.g. unreadable; needs the learner)</option>
                        <option value="unavailable">Can&apos;t be assessed (allowance returned)</option>
                      </select>
                    </label>
                    {statusOf(pos) === "pending" && (
                      <select
                        aria-label={`Ask the learner about question ${pos}`}
                        value={status[pos]?.learner_action ?? ""}
                        disabled={!canMark}
                        onChange={(e) => setStatus((s) => ({ ...s, [pos]: { ...s[pos], status: "pending", reason: s[pos]?.reason ?? "", learner_action: e.target.value || undefined } }))}
                        className="rounded border border-border bg-surface px-2 py-1"
                      >
                        <option value="">Don&apos;t ask the learner</option>
                        <option value="rescan">Ask for a clearer copy (7 days)</option>
                        <option value="confirm_or_rescan">Looks blank: confirm or clearer copy (7 days)</option>
                      </select>
                    )}
                    {statusOf(pos) !== "scored" && (
                      <input
                        aria-label={`Reason for question ${pos}`}
                        placeholder="Reason shown to the learner"
                        value={status[pos]?.reason ?? ""}
                        disabled={!canMark}
                        onChange={(e) => setStatus((s) => ({ ...s, [pos]: { ...s[pos], status: statusOf(pos), reason: e.target.value } }))}
                        className="min-w-60 flex-1 rounded border border-border bg-surface px-2 py-1"
                        maxLength={500}
                      />
                    )}
                  </div>
                )}
                {statusOf(pos) === "scored" && (body.subparts.length ? body.subparts : [{ id: "*", label: "Answer", blocks: [], max_units: q.max_units }]).map((sp) => {
                  const slot = slots[`${pos}:${sp.id}`] ?? {};
                  const crit = r.criteria.filter((cr) => (cr.subpart_id ?? "*") === sp.id);
                  return (
                    <div key={sp.id} className="space-y-2 border-t border-border pt-3">
                      <p className="text-sm">
                        <span className="font-medium">{sp.label}</span>{" "}
                        <span className="text-muted">
                          {slot.unanswered ? "· learner declared this part unanswered" : slot.pages?.length ? `· on page ${slot.pages.map(pageNo).join(", ")}` : "· no page mapped"}
                        </span>
                      </p>
                      {crit.map((cr) => (
                        <fieldset key={cr.id} className="space-y-1 rounded-lg bg-surface-muted p-2" disabled={!canMark}>
                          <legend className="text-sm">
                            <span className="font-mono text-xs text-muted">{cr.id}</span> {cr.description}
                            {disputed.has(cr.id) && <Badge tone="warn">Disputed</Badge>}
                            {cr.alternative_group ? <span className="text-xs text-muted"> (alternative route {cr.alternative_group})</span> : null}
                          </legend>
                          <div className="flex flex-wrap gap-3 text-sm" role="radiogroup" aria-label={`Award for ${cr.id}`}>
                            {[...cr.levels].sort((a, b) => a - b).map((lv) => (
                              <label key={lv} className="flex items-center gap-1">
                                <input type="radio" name={`${pos}-${cr.id}`} checked={awards[pos]?.[cr.id]?.units === lv} onChange={() => set(pos, cr.id, { units: lv })} />
                                {marks(lv)}
                              </label>
                            ))}
                          </div>
                          <input
                            aria-label={`Reason for ${cr.id}`}
                            placeholder="Reason (shown to the learner)"
                            value={awards[pos]?.[cr.id]?.reason ?? ""}
                            onChange={(e) => set(pos, cr.id, { reason: e.target.value })}
                            className="w-full rounded border border-border bg-surface px-2 py-1 text-sm"
                            maxLength={1000}
                          />
                        </fieldset>
                      ))}
                    </div>
                  );
                })}
                {(r.consequential_error_rule || r.units_rule || r.crossed_out_rule) && (
                  <details className="text-sm text-muted">
                    <summary>Marking rules</summary>
                    {r.consequential_error_rule && <p>Carried-forward errors: {r.consequential_error_rule}</p>}
                    {r.units_rule && <p>Units: {r.units_rule}</p>}
                    {r.crossed_out_rule && <p>Crossed-out work: {r.crossed_out_rule}</p>}
                  </details>
                )}
              </article>
            );
          })}
          {added.length > 0 && (
            <div className="space-y-1 rounded-xl border border-warn bg-surface p-3">
              <label htmlFor="expansion-reason" className="text-sm font-medium">
                Why are you adding question {added.join(", ")} to this recheck?
              </label>
              <textarea id="expansion-reason" value={expansionReason} onChange={(e) => setExpansionReason(e.target.value)} rows={2} maxLength={1000} className="w-full rounded border border-border bg-surface px-2 py-1 text-sm" />
              <button type="button" onClick={() => setAdded([])} className="text-sm underline">
                Undo additions
              </button>
            </div>
          )}
          <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-3">
            <span className="font-semibold">
              Total {marks(total)} / {marks(c.max_units)}
            </span>
            {canMark ? (
              <div className="flex gap-2">
                <button type="button" disabled={pending} onClick={() => run(() => saveMarks(c.id, c.version, sent(), false, expansion(), sentStatus(), classes, evidence()))} className="rounded-lg border border-border px-4 py-2 font-medium disabled:opacity-60">
                  Save marks
                </button>
                <button type="button" disabled={pending} onClick={() => run(() => saveMarks(c.id, c.version, sent(), true, expansion(), sentStatus(), classes, evidence()))} className="rounded-lg bg-accent px-4 py-2 font-medium text-white disabled:opacity-60 dark:text-background">
                  Release result
                </button>
              </div>
            ) : c.status === "released" ? (
              <Notice tone="ok" title="Released">The learner can see these marks.</Notice>
            ) : (
              <span className="text-sm text-muted">Start marking to award marks.</span>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
