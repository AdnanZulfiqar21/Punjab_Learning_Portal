import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { Adjudication, RegradeAttempts } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";
import { RunRegrade } from "./run-regrade";

export const metadata: Metadata = { title: "Rubric correction", robots: { index: false } };

const OUTCOME: Record<string, string> = {
  carried: "marks carried forward",
  review: "sent to a teacher to re-mark",
  review_in_open_case: "re-targeted in an open case",
  retargeted: "to be marked with the corrected rubric",
};
const CRITERION: Record<string, string> = { unchanged: "unchanged", changed: "changed", added: "added", removed: "removed" };
const PAGE = 25;

export default function AdjudicationPage({ params, searchParams }: PageProps<"/studio/adjudications/[id]">) {
  return (
    <div className="space-y-6">
      <Link href="/studio/adjudications" className="text-sm text-accent underline-offset-2 hover:underline">
        ← All rubric corrections
      </Link>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading the correction" />}>
        {Promise.all([params, searchParams]).then(([{ id }, sp]) => (
          <Detail id={id} offset={Math.max(0, Number(typeof sp.offset === "string" ? sp.offset : 0) || 0)} />
        ))}
      </Suspense>
    </div>
  );
}

async function Detail({ id, offset }: { id: string; offset: number }) {
  let token: string;
  try {
    ({ token } = await requireStaff(`/studio/adjudications/${id}`));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const res = await api<Adjudication>(`/v1/studio/written/adjudications/${id}`, { token });
  if (!res.ok) notFound();
  const a = res.data;
  const im = (a.impact ?? {}) as Record<string, number | Record<string, number>>;
  const n = (k: string) => Number(im[k] ?? 0);
  const applied = (im.applied_outcomes ?? {}) as Record<string, number>;
  const page = await api<RegradeAttempts>(`/v1/studio/written/adjudications/${id}/attempts?offset=${offset}&limit=${PAGE}`, { token });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Rubric correction</h1>
        <Badge tone={a.status === "active" ? "ok" : "info"}>{a.status === "active" ? "Active" : "Superseded"}</Badge>
      </div>
      <p>{a.reason}</p>
      {a.supersedes_ids.length > 0 && <p className="text-sm text-muted">Replaces {a.supersedes_ids.map((s) => s.slice(0, 8)).join(", ")}.</p>}
      <section aria-labelledby="compat-h" className="space-y-2">
        <h2 id="compat-h" className="font-semibold">
          What changed
        </h2>
        {Object.entries(a.compatibility).map(([vid, c]) => {
          const cc = c as { number: number; criteria: Record<string, string>; rubric_fields_changed: string[]; carry_forward: boolean };
          return (
            <div key={vid} className="rounded-lg border border-border bg-surface p-3 text-sm">
              <p className="font-medium">
                From version {cc.number}: {cc.carry_forward ? "scoring basis identical — marks carry forward" : "scoring basis changed — teachers re-mark"}
              </p>
              <ul>
                {Object.entries(cc.criteria).map(([cid, v]) => (
                  <li key={cid}>
                    Criterion {cid}: {CRITERION[v] ?? v}
                  </li>
                ))}
                {cc.rubric_fields_changed.length > 0 && <li>Rubric rules changed: {cc.rubric_fields_changed.join(", ")}</li>}
              </ul>
            </div>
          );
        })}
      </section>
      <section aria-labelledby="impact-h" className="space-y-2">
        <h2 id="impact-h" className="font-semibold">
          Progress
        </h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm" aria-label="Correction progress">
          <dt className="text-muted">Submitted scripts affected</dt>
          <dd>
            {n("total_attempts")} on {n("forms")} test(s); {n("released_results")} with released results; {n("evidence_revisions")} clearer cop(ies)
          </dd>
          <dt className="text-muted">Processed</dt>
          <dd>{n("processed")}</dd>
          <dt className="text-muted">Remaining</dt>
          <dd>{n("remaining")}</dd>
          <dt className="text-muted">Failed</dt>
          <dd>{n("failed")}</dd>
          <dt className="text-muted">Unaffected when processed</dt>
          <dd>{n("unaffected")}</dd>
          <dt className="text-muted">Applied so far</dt>
          <dd>
            {Object.keys(applied).length === 0
              ? "nothing yet"
              : Object.entries(applied)
                  .map(([k, v]) => `${v} question(s) ${OUTCOME[k] ?? k}`)
                  .join("; ")}
          </dd>
        </dl>
      </section>
      {a.status === "active" ? (
        <RunRegrade id={a.id} initialJob={a.latest_job ?? null} />
      ) : (
        <Notice title="Superseded">A later correction replaced this one; its run applies the complete current set.</Notice>
      )}
      {page.ok && page.data.total > 0 && (
        <section aria-labelledby="scripts-h" className="space-y-2">
          <h2 id="scripts-h" className="font-semibold">
            Processed scripts
          </h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm" aria-label="Processed scripts">
            {page.data.items.map((r) => {
              const row = r as { reference: string; status: string; outcomes: Record<string, string>; error: string | null };
              return (
                <li key={row.reference} className="px-3 py-2">
                  Script {row.reference} · {row.status === "failed" ? `failed: ${row.error}` : Object.keys(row.outcomes).length === 0 ? "unaffected" : Object.entries(row.outcomes).map(([p, o]) => `Q${p} ${OUTCOME[o] ?? o}`).join(", ")}
                </li>
              );
            })}
          </ul>
          <div className="flex gap-3 text-sm">
            {offset > 0 && <Link href={`/studio/adjudications/${a.id}?offset=${Math.max(0, offset - PAGE)}`}>← Previous</Link>}
            {offset + PAGE < page.data.total && <Link href={`/studio/adjudications/${a.id}?offset=${offset + PAGE}`}>Next →</Link>}
          </div>
        </section>
      )}
    </div>
  );
}
