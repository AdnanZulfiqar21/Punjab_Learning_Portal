import type { Metadata } from "next";
import { Suspense } from "react";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";
import { ImportWorkspace } from "./import-workspace";

export const metadata: Metadata = { title: "Import content", robots: { index: false } };

export default function ImportPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Content studio" }, { label: "Import" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Import content</h1>
        <p className="text-muted">
          Preview a JSON or CSV file first: every row is checked and nothing is written. Committing creates or updates drafts only. Imported items still need review before
          publication.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={3} label="Loading" />}>
        <Gate />
      </Suspense>
    </div>
  );
}

async function Gate() {
  let canDraft = false;
  try {
    const { me } = await requireStaff("/studio/imports");
    canDraft = me.roles.includes("content_author");
  } catch (e) {
    if (!(e instanceof StudioForbiddenError)) throw e;
  }
  if (!canDraft) return <Notice tone="warn" title="Content authors only">Only content authors can import drafts.</Notice>;
  return <ImportWorkspace />;
}
