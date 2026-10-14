import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import { Suspense } from "react";
import type { Concept, InclusionCoverage, InclusionRecord, InclusionReport } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { STUDIO_ROLES } from "@/lib/studio";
import { DraftRecord, PublishRecord } from "./inclusion-forms";

export const metadata: Metadata = { title: "Syllabus mapping", robots: { index: false } };

const SCOPES: [string, string][] = [
  ["full_curriculum", "Full curriculum"],
  ["board_syllabus", "Board syllabus"],
  ["mdcat", "MDCAT"],
  ["ecat", "ECAT"],
];
const STATE_LABEL: Record<string, string> = { included: "included", excluded: "excluded", not_applicable: "not applicable", unverified: "unverified" };

// P05.S2 (INCLUSION-01): which concepts each syllabus includes, reviewed against its source, and the published content
// behind the included ones. Content available is never shown as syllabus coverage claimed.
export default function InclusionPage({ searchParams }: PageProps<"/studio/inclusion">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Syllabus mapping" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Syllabus mapping</h1>
        <p className="text-muted">
          For each syllabus and year, record whether each published concept is included, excluded, not applicable or still unverified, with the
          source and its version. An independent subject reviewer publishes each record.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Loading syllabus mapping" />}>
        {searchParams.then((sp) => {
          const subject = typeof sp.subject === "string" && SUBJECTS.some(([c]) => c === sp.subject) ? sp.subject : "biology";
          const scope = typeof sp.scope === "string" && SCOPES.some(([c]) => c === sp.scope) ? sp.scope : "mdcat";
          const year = typeof sp.year === "string" && /^20\d\d$/.test(sp.year) ? sp.year : null;
          return <Board subject={subject} scope={scope} chosenYear={year} />;
        })}
      </Suspense>
    </div>
  );
}

async function Board({ subject, scope, chosenYear }: { subject: string; scope: string; chosenYear: string | null }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/studio/inclusion");
  // The current year is a request-time value, never read while the page is prerendered or prefetched.
  await connection();
  const year = chosenYear ?? String(new Date().getFullYear());
  if (!user.me.roles.some((r) => STUDIO_ROLES.has(r))) return <Notice tone="warn" title="Staff only">Syllabus mapping is for content staff.</Notice>;
  const yearly = scope !== "full_curriculum";
  const qs = new URLSearchParams({ subject, scope, ...(yearly ? { year } : {}) });
  const [coverage, report, records, concepts] = await Promise.all([
    api<InclusionCoverage>(`/v1/studio/inclusion/coverage?${qs}`, { token: user.token }),
    api<InclusionReport>(`/v1/studio/inclusion/report?${qs}`, { token: user.token }),
    api<InclusionRecord[]>(`/v1/studio/inclusion?${qs}`, { token: user.token }),
    api<Concept[]>(`/v1/studio/concepts?subject=${subject}`, { token: user.token }),
  ]);
  const author = user.me.roles.includes("content_author");
  const reviewer = user.me.roles.includes("subject_reviewer");
  const mapped = new Set((records.ok ? records.data : []).map((r) => r.concept_id));
  const draftable = (concepts.ok ? concepts.data : []).filter((c) => c.status === "published" && !mapped.has(c.id));
  return (
    <div className="space-y-6">
      <form method="get" aria-label="Choose a syllabus" className="flex flex-wrap items-end gap-2 text-sm">
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
        <label className="flex flex-col gap-1">
          Syllabus
          <select name="scope" defaultValue={scope} className="rounded-lg border border-border bg-surface px-2 py-2">
            {SCOPES.map(([c, n]) => (
              <option key={c} value={c}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Year
          <input name="year" type="number" min={2020} max={2100} defaultValue={year} className="w-28 rounded-lg border border-border bg-surface px-2 py-2" />
        </label>
        <button type="submit" className="rounded-lg border border-border bg-surface px-3 py-2 hover:border-accent">
          Show
        </button>
      </form>

      <section aria-labelledby="coverage-h" className="space-y-2">
        <h2 id="coverage-h" className="font-semibold">
          Coverage
        </h2>
        {coverage.ok ? (
          <>
            <p className="text-sm">
              {coverage.data.included} included concept{coverage.data.included === 1 ? "" : "s"} · {coverage.data.with_lessons} with live lessons · {coverage.data.with_questions} with
              practice questions · {coverage.data.with_lectures} with approved lectures
            </p>
            {coverage.data.concepts.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-border bg-surface">
                <table className="w-full text-sm">
                  <thead className="text-left text-muted">
                    <tr>
                      {["Concept", "State", "Lessons", "Questions", "Lectures"].map((h) => (
                        <th key={h} scope="col" className="px-3 py-2 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {coverage.data.concepts.map((c) => (
                      <tr key={c.concept_id}>
                        <th scope="row" className="px-3 py-2 text-left font-normal">
                          <Link href={`/studio/concepts/${c.concept_id}`} className="text-accent underline underline-offset-2">
                            {c.title}
                          </Link>
                        </th>
                        <td className="px-3 py-2">{c.state ? STATE_LABEL[c.state] : <span className="text-muted">no record</span>}</td>
                        <td className="px-3 py-2 tabular-nums">{c.live_lessons}</td>
                        <td className="px-3 py-2 tabular-nums">{c.live_questions}</td>
                        <td className="px-3 py-2 tabular-nums">{c.approved_lectures}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <Notice tone="warn" title="Couldn't load coverage">{coverage.problem?.detail ?? "Please try again."}</Notice>
        )}
      </section>

      {report.ok && (
        <section aria-labelledby="report-h" className="space-y-2">
          <h2 id="report-h" className="font-semibold">
            Needs attention
          </h2>
          {report.data.unmapped.length === 0 && report.data.contradictions.length === 0 ? (
            <p className="text-sm text-muted">Every published concept has a published record here, and nothing contradicts.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {report.data.contradictions.map((x) => (
                <li key={`c-${x.concept_id}`}>
                  <Badge tone="warn">contradiction</Badge> <span className="font-mono text-xs">{x.code}</span> {x.detail}
                </li>
              ))}
              {report.data.unmapped.map((x) => (
                <li key={`u-${x.concept_id}`}>
                  <Badge>no record</Badge> <span className="font-mono text-xs">{x.code}</span> {x.title}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section aria-labelledby="records-h" className="space-y-2">
        <h2 id="records-h" className="font-semibold">
          Records
        </h2>
        {records.ok && records.data.length > 0 ? (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {records.data.map((r) => (
              <li key={r.id} className="space-y-1 p-3">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.concept_title}</span>
                  <Badge tone={r.status === "published" ? "ok" : "warn"}>{r.status}</Badge>
                  <span>{STATE_LABEL[r.state]}</span>
                </p>
                <p className="text-muted">
                  {r.reason} · Source: {r.source} ({r.source_version})
                </p>
                {reviewer && r.status === "draft" && <PublishRecord id={r.id} />}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No records for this syllabus and year yet.</p>
        )}
        {author && (
          <DraftRecord concepts={draftable.map((c) => ({ id: c.id, label: `${c.title} (${c.code})` }))} scope={scope} year={yearly ? year : ""} />
        )}
      </section>
    </div>
  );
}
