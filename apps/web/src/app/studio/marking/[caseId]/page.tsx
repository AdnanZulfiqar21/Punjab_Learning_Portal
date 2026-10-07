import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { MarkingCase } from "@portal/contracts";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { requireStaff, StudioForbiddenError } from "@/lib/studio";
import { MarkingWorkspace } from "./marking-workspace";

export const metadata: Metadata = { title: "Mark a script", robots: { index: false } };

export default function MarkingCasePage({ params }: PageProps<"/studio/marking/[caseId]">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio/marking", label: "Written marking" }, { label: "Script" }]} />
      <Suspense fallback={<SkeletonLines lines={8} label="Loading the script" />}>
        {params.then(({ caseId }) => (
          <Case id={caseId} />
        ))}
      </Suspense>
    </div>
  );
}

async function Case({ id }: { id: string }) {
  let token: string;
  try {
    ({ token } = await requireStaff(`/studio/marking/${id}`));
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const res = await api<MarkingCase>(`/v1/studio/written/cases/${id}`, { token });
  if (!res.ok) notFound();
  return <MarkingWorkspace key={`${res.data.id}:${res.data.version}:${res.data.status}`} initial={res.data} />;
}
