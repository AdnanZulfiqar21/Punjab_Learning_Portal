"use client";

// Teacher marking workspace (W06.S1): evidence beside the pinned question and rubric. Awards are limited to the
// rubric's permitted levels; the API re-checks levels, unanswered parts, dependencies, alternative routes, the lease and
// the expected version, so a stale or conflicting decision is reported, never silently applied.
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { MarkingCase } from "@portal/contracts";
import { saveMarks, takeLease } from "@/app/actions/marking";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Notice } from "@/components/ui";

type Criterion = { id: string; subpart_id: string | null; description: string; max_units: number; levels: number[]; alternative_group?: string | null };
type Rubric = { criteria: Criterion[]; expected_concepts?: string[]; consequential_error_rule?: string; units_rule?: string; crossed_out_rule?: string };
type Question = { stem: { type: string }[]; subparts: { id: string; label: string; blocks: { type: string }[]; max_units: number }[] };
type Awards = Record<string, Record<string, { units: number; reason: string }>>;
const marks = (u: number) => String(u / 100);

export function MarkingWorkspace({ initial }: { initial: MarkingCase }) {
  const router = useRouter();
  const [c, setC] = useState(initial);
  const [pending, start] = useTransition();
  const [error, setError] = useState<{ text: string; list?: string[]; conflict?: boolean } | null>(null);
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
  const slots = (c.manifest as { slots?: Record<string, { pages?: string[]; unanswered?: boolean }> }).slots ?? {};
  const pageNo = (id: string) => c.pages.findIndex((p) => p.id === id) + 1;
  const total = Object.values(awards).reduce((n, q) => n + Object.values(q).reduce((m, a) => m + a.units, 0), 0);
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
      } else setError({ text: out.error, list: out.errors, conflict: out.conflict });
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Script {c.reference}</h1>
          <p className="text-sm text-muted">
            {c.case_kind === "recheck" ? "Recheck" : "First marking"} · out of {marks(c.max_units)} marks · version {c.version}
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
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-label="Submitted pages" className="space-y-3">
          {c.pages.map((p, i) =>
            p.content_type.startsWith("image/") ? (
              <figure key={p.id} className="rounded-lg border border-border bg-surface p-2">
                {/* eslint-disable-next-line @next/next/no-img-element -- private evidence served by our own route */}
                <img src={`/studio/marking/${c.id}/pages/${p.id}`} alt={`Submitted page ${i + 1}`} className="w-full rounded" />
                <figcaption className="mt-1 text-sm text-muted">Page {i + 1}</figcaption>
              </figure>
            ) : (
              <a key={p.id} href={`/studio/marking/${c.id}/pages/${p.id}`} target="_blank" rel="noreferrer" className="block rounded-lg border border-border bg-surface p-4 underline">
                Page {i + 1}: PDF, {p.pdf_pages} page(s)
              </a>
            ),
          )}
        </section>

        <section aria-label="Marks" className="space-y-4">
          {c.questions.map((q) => {
            const pos = String(q.position);
            const r = q.rubric as unknown as Rubric;
            const body = q.question as unknown as Question;
            const qTotal = Object.values(awards[pos] ?? {}).reduce((n, a) => n + a.units, 0);
            return (
              <article key={pos} className="space-y-3 rounded-xl border border-border bg-surface p-4">
                <div className="flex justify-between">
                  <h2 className="font-semibold">Question {pos}</h2>
                  <span className="text-sm">
                    {marks(qTotal)} / {marks(q.max_units)}
                  </span>
                </div>
                <LessonBlocks blocks={body.stem} headingOffset={2} />
                {(body.subparts.length ? body.subparts : [{ id: "*", label: "Answer", blocks: [], max_units: q.max_units }]).map((sp) => {
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
          <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-3">
            <span className="font-semibold">
              Total {marks(total)} / {marks(c.max_units)}
            </span>
            {canMark ? (
              <div className="flex gap-2">
                <button type="button" disabled={pending} onClick={() => run(() => saveMarks(c.id, c.version, awards, false))} className="rounded-lg border border-border px-4 py-2 font-medium disabled:opacity-60">
                  Save marks
                </button>
                <button type="button" disabled={pending} onClick={() => run(() => saveMarks(c.id, c.version, awards, true))} className="rounded-lg bg-accent px-4 py-2 font-medium text-white disabled:opacity-60 dark:text-background">
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
