import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { SearchTermGroup } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { STUDIO_ROLES } from "@/lib/studio";
import { ProposeTerms, TermActions } from "./search-term-forms";

export const metadata: Metadata = { title: "Search terms", robots: { index: false } };

const LANGUAGE_NAME: Record<string, string> = { en: "English", ur: "Urdu", roman_ur: "Roman Urdu" };
const STATUS: Record<string, { label: string; tone: "ok" | "warn" | "info" }> = {
  approved: { label: "In use", tone: "ok" },
  proposed: { label: "Waiting for a second person", tone: "warn" },
  retired: { label: "Retired", tone: "info" },
};

// P11.S2.T3 (SEARCH-01): equivalent terms in English, Urdu script and Roman Urdu, so a learner searching in one finds
// lessons written in another. Every group comes from the owner's material and is used only once someone else approves it.
export default function SearchTermsPage({ searchParams }: PageProps<"/studio/search-terms">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Search terms" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Search terms</h1>
        <p className="text-muted">
          Groups of the same term in English, Urdu and Roman Urdu spellings, taken from the owner&apos;s material. Search uses a group once a subject
          reviewer who didn&apos;t propose it approves it. Retired groups stay on record.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading search terms" />}>
        {searchParams.then((sp) => {
          const subject = typeof sp.subject === "string" && SUBJECTS.some(([c]) => c === sp.subject) ? sp.subject : "biology";
          return <Terms grade={sp.grade === "12" ? "12" : "11"} subject={subject} />;
        })}
      </Suspense>
    </div>
  );
}

async function Terms({ grade, subject }: { grade: string; subject: string }) {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/studio/search-terms");
  if (!user.me.roles.some((r) => STUDIO_ROLES.has(r))) return <Notice tone="warn" title="Staff only">Search terms are for content staff.</Notice>;
  const res = await api<SearchTermGroup[]>(`/v1/studio/search-terms?grade=${grade}&subject=${subject}`, { token: user.token });
  return (
    <div className="space-y-6">
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
        <Notice tone="warn" title="Not available">
          {res.problem?.detail ?? "This class and subject are outside your role's scope."}
        </Notice>
      ) : (
        <>
          {user.me.roles.includes("content_author") && <ProposeTerms grade={grade} subject={subject} />}
          <section aria-labelledby="groups-h" className="space-y-2">
            <h2 id="groups-h" className="font-semibold">
              Groups
            </h2>
            {res.data.length === 0 ? (
              <p className="text-sm text-muted">No search terms for this class and subject yet. They come from the owner&apos;s material.</p>
            ) : (
              <ul className="space-y-2">
                {res.data.map((g) => (
                  <li key={g.id} className="space-y-2 rounded-xl border border-border bg-surface px-4 py-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={STATUS[g.status]?.tone ?? "info"}>{STATUS[g.status]?.label ?? g.status}</Badge>
                      {g.mine && <span className="text-muted">Proposed by you</span>}
                    </div>
                    <ul className="flex flex-wrap gap-x-4 gap-y-1">
                      {g.forms.map((f) => (
                        <li key={`${f.language}-${f.text}`}>
                          <span className="text-muted">{LANGUAGE_NAME[f.language] ?? f.language}: </span>
                          <span lang={f.language === "ur" ? "ur" : undefined} dir={f.language === "ur" ? "rtl" : undefined} className="font-medium">
                            {f.text}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <p className="text-muted">Source: {g.source_ref}</p>
                    {g.retired_reason && <p className="text-muted">Retired: {g.retired_reason}</p>}
                    {(g.can_approve || g.can_retire) && <TermActions id={g.id} canApprove={g.can_approve} canRetire={g.can_retire} />}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
