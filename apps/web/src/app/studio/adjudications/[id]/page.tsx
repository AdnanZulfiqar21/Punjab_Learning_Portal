import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { Adjudication } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";
import { RunRegrade } from "./run-regrade";

export const metadata: Metadata = { title: "Rubric correction", robots: { index: false } };

const OUTCOME: Record<string, string> = {
  carried: "marks carried forward (scoring basis identical)",
  review: "to be re-marked by a teacher",
  retargeted: "to be marked with the corrected rubric",
};
const CRITERION: Record<string, string> = { unchanged: "unchanged", changed: "changed", added: "added", removed: "removed" };

export default function AdjudicationPage({ params }: PageProps<"/studio/adjudications/[id]">) {
  return (
    <div className="space-y-6">
      <Link href="/studio/adjudications" className="text-sm text-accent underline-offset-2 hover:underline">
        ← All rubric corrections
      </Link>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading the correction" />}>
        {params.then(({ id }) => (
          <Detail id={id} />
        ))}
      </Suspense>
    </div>
  );
}

async function Detail({ id }: { id: string }) {
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
  const outcomes = a.impact.question_outcomes as Record<string, number>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Rubric correction</h1>
        <Badge tone={a.status === "active" ? "ok" : "info"}>{a.status === "active" ? "Active" : "Superseded"}</Badge>
      </div>
      <p>{a.reason}</p>
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
          Impact
        </h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">Still to apply</dt>
          <dd>
            {String(a.impact.attempts)} attempt(s) on {String(a.impact.forms)} test(s), {String(a.impact.released_results)} with released results,{" "}
            {String(a.impact.evidence_revisions)} clearer cop(ies) on affected questions
          </dd>
          <dt className="text-muted">Planned</dt>
          <dd>
            {Object.keys(outcomes).length === 0
              ? "nothing left to apply"
              : Object.entries(outcomes)
                  .map(([k, n]) => `${n} question(s) ${OUTCOME[k] ?? k}`)
                  .join("; ")}
          </dd>
          <dt className="text-muted">Processed</dt>
          <dd>{String(a.impact.processed_attempts)} attempt(s)</dd>
        </dl>
      </section>
      {a.status === "active" ? (
        <RunRegrade id={a.id} />
      ) : (
        <Notice title="Superseded">A later correction replaced this one; its run applies the complete current set.</Notice>
      )}
    </div>
  );
}
