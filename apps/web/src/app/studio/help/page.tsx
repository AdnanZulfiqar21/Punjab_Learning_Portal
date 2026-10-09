import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { StaffHelpArticle } from "@portal/contracts";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { requireSupportStaff, StudioForbiddenError } from "@/lib/studio";
import { DraftForm, PublishButton } from "./help-forms";

export const metadata: Metadata = { title: "Help articles (staff)", robots: { index: false } };

export default function StudioHelpPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Help articles</h1>
        <p className="text-muted">
          Saving makes a new draft version; readers see only published versions. Publishing needs a multi-factor sign-in.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={5} label="Loading articles" />}>
        <List />
      </Suspense>
    </div>
  );
}

async function List() {
  let token: string;
  try {
    ({ token } = await requireSupportStaff("/studio/help"));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  const res = await api<StaffHelpArticle[]>("/v1/studio/help/articles", { token });
  if (!res.ok) return <Notice tone="warn" title="Help-centre staff only">Only help-centre staff can edit help articles.</Notice>;
  return (
    <div className="space-y-6">
      <ul className="divide-y divide-border rounded-xl border border-border bg-surface" aria-label="Help articles">
        {res.data.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="font-medium">
                {a.title} <span className="text-sm text-muted">({a.locale})</span>
              </p>
              <p className="text-sm text-muted">
                {a.slug} · draft version {a.working_version}
                {a.published && (
                  <>
                    {" · "}
                    <Link href={`/help/articles/${a.slug}`} className="text-accent underline">
                      published
                    </Link>
                  </>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={a.status === "published" ? "ok" : "info"}>{a.status}</Badge>
              {a.unpublished_changes && a.status !== "retired" && <PublishButton id={a.id} action="publish" />}
              {a.status === "published" && <PublishButton id={a.id} action="retire" />}
            </div>
          </li>
        ))}
      </ul>
      <section aria-labelledby="draft-h" className="space-y-2">
        <h2 id="draft-h" className="font-semibold">
          Write or update an article
        </h2>
        <DraftForm />
      </section>
    </div>
  );
}
