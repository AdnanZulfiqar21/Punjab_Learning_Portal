import type { Metadata } from "next";
import { Suspense } from "react";
import type { Calibration } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";
import { AdjudicateComparison } from "./adjudicate-form";

export const metadata: Metadata = { title: "Calibration", robots: { index: false } };

const STATUS: Record<string, { label: string; tone: "ok" | "warn" | "info" }> = {
  agreed: { label: "Agreed", tone: "ok" },
  open: { label: "Disagreement to review", tone: "warn" },
  adjudicated: { label: "Adjudicated", tone: "info" },
};

// W06.S1.T3 (CALIBRATION-01): teachers mark the evaluation subset without ever seeing an automatic proposal; here an
// academic adjudicator compares the two and records who applied the rubric correctly. Nothing here changes a mark.
export default function CalibrationPage({ searchParams }: PageProps<"/studio/calibration">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Calibration" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Calibration</h1>
        <p className="text-muted">
          Blinded teacher marks compared with automatic proposals on the evaluation subset. Automatic marking stays off for learners; this is evidence for
          its reliability review only, and nothing here changes a teacher&apos;s marks or a learner&apos;s result.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading calibration" />}>
        {searchParams.then((sp) => {
          const subject = typeof sp.subject === "string" && SUBJECTS.some(([c]) => c === sp.subject) ? sp.subject : "biology";
          return <Board grade={sp.grade === "12" ? "12" : "11"} subject={subject} />;
        })}
      </Suspense>
    </div>
  );
}

async function Board({ grade, subject }: { grade: string; subject: string }) {
  let token: string;
  try {
    ({ token } = await requireStaff("/studio/calibration"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const res = await api<Calibration>(`/v1/studio/written/calibration?grade=${grade}&subject=${subject}`, { token });
  return (
    <div className="space-y-4">
      <form method="get" aria-label="Choose class and subject" className="flex flex-wrap items-end gap-2 text-sm">
        <label className="flex flex-col gap-1">
          Class
          <select name="grade" defaultValue={grade} className="rounded-lg border border-border bg-surface px-2 py-2">
            <option value="11">Class XI</option>
            <option value="12">Class XII</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Subject
          <select name="subject" defaultValue={subject} className="rounded-lg border border-border bg-surface px-2 py-2">
            {SUBJECTS.map(([c, n]) => (
              <option key={c} value={c}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent">
          Show
        </button>
      </form>
      {!res.ok ? (
        <Notice tone="warn" title="Academic adjudicators only">
          {res.problem?.detail ?? "Calibration is for academic adjudicators in this class and subject, with a multi-factor sign-in."}
        </Notice>
      ) : res.data.compared === 0 ? (
        <Notice title="Nothing to compare yet">
          Comparisons appear once a teacher has released marks for a script in the evaluation subset ({res.data.evaluation_percent}% of scripts) that also
          has an automatic proposal. Automatic assessment is off until a provider is approved.
        </Notice>
      ) : (
        <>
          <p className="text-sm text-muted">
            {res.data.compared} compared · {res.data.agreed} agreed · {res.data.disagreed} disagreed · {res.data.adjudicated} adjudicated
            {res.data.agreement_rate !== null && ` · agreement ${Math.round(res.data.agreement_rate * 100)}%`} · evaluation subset{" "}
            {res.data.evaluation_percent}%
          </p>
          <ul className="space-y-3">
            {res.data.comparisons.map((c) => (
              <li key={c.id} className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    Script {c.reference} · question {c.position}
                  </p>
                  <Badge tone={STATUS[c.status]?.tone ?? "info"}>{STATUS[c.status]?.label ?? c.status}</Badge>
                </div>
                <table className="text-left">
                  <caption className="sr-only">
                    Teacher and proposal awards, script {c.reference} question {c.position}
                  </caption>
                  <thead className="text-muted">
                    <tr>
                      <th className="pr-4 font-normal">Criterion</th>
                      <th className="pr-4 font-normal">Teacher</th>
                      <th className="font-normal">Proposal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys({ ...c.teacher_units, ...c.proposal_units }).map((k) => (
                      <tr key={k} className={c.disagreements.includes(k) ? "font-medium" : undefined}>
                        <td className="pr-4 font-mono">{k}</td>
                        <td className="pr-4">{c.teacher_units[k] ?? "—"}</td>
                        <td>{c.proposal_units[k] ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {c.status === "adjudicated" && (
                  <p className="text-muted">
                    Verdicts: {Object.entries(c.verdicts).map(([k, v]) => `${k}: ${v}`).join(", ")}. {c.reason}
                  </p>
                )}
                {c.status === "open" && <AdjudicateComparison id={c.id} criteria={c.disagreements} />}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
