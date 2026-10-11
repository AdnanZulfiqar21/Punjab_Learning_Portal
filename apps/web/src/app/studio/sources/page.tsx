import type { Metadata } from "next";
import { Suspense } from "react";
import type { SourceInfo, SyllabusNotice } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { redirect } from "next/navigation";
import { api, currentUser } from "@/lib/session";
import { STUDIO_ROLES } from "@/lib/studio";
import { DecideNotice, LogNoticeForm, ReviewSourceButton, RightsForm, UploadOriginal, ViewSourcePage } from "./controls";

export const metadata: Metadata = { title: "Sources and notices", robots: { index: false } };
const date = (s: string) => new Date(s).toLocaleDateString("en-GB", { dateStyle: "medium" });

export default function SourcesPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Content studio" }, { label: "Sources and notices" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Sources and notices</h1>
        <p className="text-muted">
          The official books behind every item, when they were last checked, and syllabus notices waiting for a subject reviewer. Notices never change content by themselves.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={8} label="Loading sources" />}>
        <Body />
      </Suspense>
    </div>
  );
}

async function Body() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/studio/sources");
  const { token } = user;
  const roles = user.me.roles;
  const staff = roles.some((r) => STUDIO_ROLES.has(r));
  const owner = roles.includes("owner_admin"); // SOURCE-INTAKE-01: the owner sets rights and stores originals
  if (!staff && !owner) return <Notice tone="warn" title="Staff only">Only content staff and the owner can open the source registry.</Notice>;
  const [sources, notices] = await Promise.all([
    api<SourceInfo[]>("/v1/studio/sources", { token }),
    staff ? api<SyllabusNotice[]>("/v1/studio/syllabus-notices", { token }) : Promise.resolve(null),
  ]);
  const reviewer = roles.includes("subject_reviewer");
  return (
    <div className="space-y-8">
      {staff && notices && (
      <section aria-labelledby="notices-h" className="space-y-3">
        <h2 id="notices-h" className="font-semibold">
          Syllabus notices
        </h2>
        <LogNoticeForm />
        {notices.ok && notices.data.length > 0 ? (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Notices">
            {notices.data.map((n) => (
              <li key={n.id} className="space-y-1 p-3 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{n.title}</span>
                  <Badge tone={n.status === "open" ? "warn" : n.status === "accepted" ? "ok" : "info"}>{n.status}</Badge>
                  <span className="text-muted">
                    Class {n.grade === 11 ? "XI" : "XII"} {n.subject.replace("_", " ")} · logged {date(n.logged_at)} · {n.live_items_in_scope} live items in scope
                  </span>
                </p>
                <p>{n.summary}</p>
                {n.source_url && (
                  <a href={n.source_url} rel="noopener noreferrer" target="_blank" className="text-accent underline underline-offset-2">
                    Official link
                  </a>
                )}
                {n.decision && <p className="text-muted">Decision: {n.decision}</p>}
                {n.can_decide && <DecideNotice id={n.id} />}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No notices yet.</p>
        )}
      </section>
      )}
      <section aria-labelledby="sources-h" className="space-y-3">
        <h2 id="sources-h" className="font-semibold">
          Source registry
        </h2>
        {!sources.ok ? (
          <Notice tone="warn" title="Couldn't load sources">
            {sources.problem?.detail ?? "Please try again."}
          </Notice>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Sources">
            {sources.data.map((s) => (
              <li key={s.id} className="space-y-1 p-3 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{s.title ?? s.source_id}</span>
                  <Badge tone={s.publication_rights === "CONFIRMED" ? "ok" : s.publication_rights === "DENIED" ? "danger" : "warn"}>rights {s.publication_rights.toLowerCase()}</Badge>
                  {s.review_stale ? <Badge tone="warn">review due</Badge> : <Badge tone="ok">reviewed</Badge>}
                  {s.original_stored ? <Badge tone="ok">original stored</Badge> : <Badge>original not stored</Badge>}
                </p>
                <p className="text-muted">
                  {s.source_id} · Class {s.grade_number === 11 ? "XI" : "XII"} {s.subject_code.replace("_", " ")} · {s.pdf_pages} pages ·{" "}
                  {s.last_reviewed_at ? `last reviewed ${date(s.last_reviewed_at)}` : "never reviewed"}
                </p>
                {reviewer && <ReviewSourceButton id={s.id} label={s.source_id} />}
                {s.original_stored && staff && <ViewSourcePage id={s.id} pages={s.pdf_pages} label={s.source_id} />}
                {owner && !s.original_stored && <UploadOriginal id={s.id} label={s.source_id} />}
                {owner && <RightsForm id={s.id} label={s.source_id} />}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
