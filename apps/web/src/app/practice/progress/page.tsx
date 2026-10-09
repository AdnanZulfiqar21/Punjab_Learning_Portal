import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { ProgressReport } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { api, currentUser } from "@/lib/session";
import { PrintButton } from "./print-button";

export const metadata: Metadata = { title: "Progress report", robots: { index: false } };

const day = (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString("en-GB", { dateStyle: "medium" }) : "—");

export default function ProgressPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Progress report" }]} />
      <Suspense fallback={<SkeletonLines lines={8} label="Preparing your report" />}>
        <Report />
      </Suspense>
    </div>
  );
}

async function Report() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/practice/progress");
  const res = await api<ProgressReport>("/v1/me/progress", { token: user.token });
  if (!res.ok) return <Notice tone="warn" title="Couldn't prepare your report">{res.problem?.detail ?? "Please try again."}</Notice>;
  const r = res.data;
  return (
    <article className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Progress report</h1>
          <p className="text-sm text-muted">
            {user.me.email} · prepared {day(r.generated_at)} · report version {r.report_version}
          </p>
        </div>
        <PrintButton />
      </div>
      {r.results_pending > 0 && (
        <Notice title="Results on the way">
          {r.results_pending} submitted scheduled mock{r.results_pending === 1 ? " is" : "s are"} waiting for the release time. They count here once released.
        </Notice>
      )}
      {r.subjects.length === 0 ? (
        r.results_pending === 0 && (
        <Notice title="No submitted tests yet">
          <Link href="/practice" className="underline">
            Take a practice test
          </Link>{" "}
          to start your report.
        </Notice>
        )
      ) : (
        <section aria-labelledby="subjects-h" className="space-y-2">
          <h2 id="subjects-h" className="font-semibold">
            By class and subject
          </h2>
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-sm">
              <thead className="text-left text-muted">
                <tr>
                  {["Class and subject", "Tests", "Answered", "Correct", "Accuracy", "Last activity"].map((h) => (
                    <th key={h} scope="col" className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {r.subjects.map((s) => (
                  <tr key={`${s.grade}-${s.subject}`}>
                    <th scope="row" className="px-3 py-2 text-left font-normal">
                      {GRADE_LABEL[s.grade]} {s.subject.replace("_", " ")}
                    </th>
                    <td className="px-3 py-2 tabular-nums">{s.tests}</td>
                    <td className="px-3 py-2 tabular-nums">{s.questions_answered}</td>
                    <td className="px-3 py-2 tabular-nums">{s.correct}</td>
                    <td className="px-3 py-2 tabular-nums">{s.accuracy === null ? "—" : `${s.accuracy}%`}</td>
                    <td className="px-3 py-2">{day(s.last_activity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {r.recent.length > 0 && (
        <section aria-labelledby="recent-h" className="space-y-2">
          <h2 id="recent-h" className="font-semibold">
            Recent results
          </h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {r.recent.map((t) => (
              <li key={t.attempt_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span>
                  {day(t.finished_at)} · {t.kind === "mock" ? "Mock" : t.kind === "review" ? "Review" : "Practice"} · {GRADE_LABEL[t.grade]} {t.subject.replace("_", " ")}
                </span>
                <span className="tabular-nums">
                  {t.status === "not_scorable" ? "Not scorable" : `${t.raw} / ${t.maximum}${t.percentage === null ? "" : ` (${t.percentage}%)`}`}
                  {t.score_version > 1 && <span className="text-muted"> · updated after review</span>}{" "}
                  <Link href={`/practice/attempt/${t.attempt_id}/result`} className="text-accent underline underline-offset-2 print:hidden">
                    Open
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section aria-labelledby="nb-h" className="space-y-1 text-sm">
        <h2 id="nb-h" className="font-semibold">
          Mistake notebook
        </h2>
        <p>
          {r.notebook.open} open · {r.notebook.mastered} mastered · {r.notebook.voided} withdrawn after review
        </p>
      </section>
      <section aria-labelledby="def-h" className="space-y-1 text-sm">
        <h2 id="def-h" className="font-semibold">
          What these numbers mean
        </h2>
        <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[max-content_1fr]">
          {Object.entries(r.definitions).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-medium">{k.replace("_", " ")}</dt>
              <dd className="text-muted">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="text-muted">This report counts what you did. It does not say which topics you have mastered.</p>
      </section>
    </article>
  );
}
