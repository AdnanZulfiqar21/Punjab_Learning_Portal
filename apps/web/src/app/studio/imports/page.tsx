import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import type { ImportBatch } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { TIME_ZONE } from "@/lib/dates";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";
import { ImportWorkspace } from "./import-workspace";

export const metadata: Metadata = { title: "Import content", robots: { index: false } };

export default function ImportPage({ searchParams }: PageProps<"/studio/imports">) {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Content studio" }, { label: "Import" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Import content</h1>
        <p className="text-muted">
          Preview a JSON, CSV or Excel file first: every row is checked and nothing is written. Committing creates or updates drafts only. Imported items still need review
          before publication.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={3} label="Loading" />}>
        {searchParams.then((sp) => (
          <Gate batch={typeof sp.batch === "string" && /^[0-9a-f-]{36}$/i.test(sp.batch) ? sp.batch : undefined} />
        ))}
      </Suspense>
    </div>
  );
}

const STATUS: Record<string, string> = {
  queued: "Queued",
  validating: "Checking",
  previewed: "Preview ready",
  committing: "Importing",
  committed: "Imported",
  discarded: "Discarded",
  failed: "Failed",
};
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });

async function Gate({ batch }: { batch?: string }) {
  let canDraft = false;
  let token = "";
  try {
    const { me, token: t } = await requireStaff("/studio/imports");
    canDraft = me.roles.includes("content_author");
    token = t;
  } catch (e) {
    if (!(e instanceof StudioForbiddenError)) throw e;
  }
  if (!canDraft) return <Notice tone="warn" title="Content authors only">Only content authors can import drafts.</Notice>;
  // IMPORT-BULK-01: a large file is checked in the background, so an author can leave and reopen it from here.
  const recent = await api<ImportBatch[]>("/v1/studio/imports", { token });
  return (
    <div className="space-y-8">
      <ImportWorkspace key={batch ?? "new"} initialBatchId={batch} />
      {recent.ok && recent.data.length > 0 && (
        <section aria-labelledby="recent-h" className="space-y-2">
          <h2 id="recent-h" className="font-semibold">
            Your recent imports
          </h2>
          <ul className="divide-y divide-border rounded-xl border border-border bg-surface text-sm">
            {recent.data.slice(0, 20).map((b) => (
              <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <span>
                  <Link href={`/studio/imports?batch=${b.id}`} className="font-medium text-accent underline underline-offset-2">
                    {b.filename}
                  </Link>{" "}
                  <span className="text-muted">· {when(b.created_at)}</span>
                </span>
                <span className="text-muted">{STATUS[b.status] ?? b.status}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
