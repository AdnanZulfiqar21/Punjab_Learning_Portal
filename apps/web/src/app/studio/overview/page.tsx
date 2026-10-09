import type { Metadata } from "next";
import { Suspense } from "react";
import type { AcademicOverview } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";

export const metadata: Metadata = { title: "Academic overview", robots: { index: false } };

const SUBJECTS: Record<string, string> = {
  biology: "Biology",
  chemistry: "Chemistry",
  physics: "Physics",
  computer_science: "Computer Science",
  mathematics: "Mathematics",
};

export default function OverviewPage({ searchParams }: PageProps<"/studio/overview">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Content studio" }, { label: "Academic overview" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Academic overview</h1>
        <p className="text-muted">What learners can use now, what is in the pipeline, and where problems are, chapter by chapter.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Loading the overview" />}>
        {searchParams.then((sp) => (
          <Overview grade={sp.grade === "12" ? "12" : "11"} subject={typeof sp.subject === "string" && SUBJECTS[sp.subject] ? sp.subject : "biology"} />
        ))}
      </Suspense>
    </div>
  );
}

async function Overview({ grade, subject }: { grade: string; subject: string }) {
  let token = "";
  try {
    ({ token } = await requireStaff("/studio/overview"));
  } catch (e) {
    if (!(e instanceof StudioForbiddenError)) throw e;
  }
  if (!token) return <Notice tone="warn" title="Staff only">Only content staff can open the academic overview.</Notice>;
  const res = await api<AcademicOverview>(`/v1/studio/overview?grade=${grade}&subject=${subject}`, { token });
  return (
    <div className="space-y-4">
      <form method="get" className="flex flex-wrap items-end gap-2" aria-label="Choose class and subject">
        <select name="grade" defaultValue={grade} aria-label="Class" className="rounded-lg border border-border bg-surface px-3 py-2">
          <option value="11">Class XI</option>
          <option value="12">Class XII</option>
        </select>
        <select name="subject" defaultValue={subject} aria-label="Subject" className="rounded-lg border border-border bg-surface px-3 py-2">
          {Object.entries(SUBJECTS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button type="submit" className="rounded-lg border border-border bg-surface px-4 py-2 font-medium hover:border-accent">
          Show
        </button>
      </form>
      {!res.ok ? (
        <Notice tone="warn" title="Not available">
          {res.problem?.detail ?? "This class and subject are outside your role's scope."}
        </Notice>
      ) : (
        <>
          <p className="text-sm text-muted">
            {res.data.chapters_with_lessons} of {res.data.chapters.length} chapters have a live lesson · {res.data.chapters_pool_sufficient} have at least {res.data.pool_rule} approved question
            families · {res.data.totals.in_review} in review · {res.data.totals.quarantined} quarantined · {res.data.totals.open_reports} open error reports
          </p>
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-sm">
              <caption className="sr-only">Chapters</caption>
              <thead className="text-left text-muted">
                <tr>
                  {["Chapter", "Lessons", "MCQ families", "Written", "Drafts", "In review", "Approved", "Quarantined", "Reports", "Pool"].map((h) => (
                    <th key={h} scope="col" className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {res.data.chapters.map((c) => (
                  <tr key={c.chapter_id}>
                    <th scope="row" className="px-3 py-2 text-left font-normal">
                      {c.number}. {c.title}
                    </th>
                    <td className="px-3 py-2 tabular-nums">{c.live_lessons}</td>
                    <td className="px-3 py-2 tabular-nums">{c.live_mcq_families}</td>
                    <td className="px-3 py-2 tabular-nums">{c.live_written}</td>
                    <td className="px-3 py-2 tabular-nums">{c.drafts}</td>
                    <td className="px-3 py-2 tabular-nums">{c.in_review}</td>
                    <td className="px-3 py-2 tabular-nums">{c.approved_unpublished}</td>
                    <td className="px-3 py-2 tabular-nums">{c.quarantined}</td>
                    <td className="px-3 py-2 tabular-nums">{c.open_reports}</td>
                    <td className="px-3 py-2">{c.pool_sufficient ? <Badge tone="ok">Enough</Badge> : <Badge tone="warn">Short</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
