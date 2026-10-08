import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import type { AdjudicationSources } from "@portal/contracts";
import { Notice, SkeletonLines } from "@/components/ui";
import { api } from "@/lib/session";
import { getItem, requireStaff, StudioForbiddenError } from "@/lib/studio";
import { NewAdjudicationForm } from "./new-form";

export const metadata: Metadata = { title: "Apply a rubric correction", robots: { index: false } };

export default function NewAdjudicationPage({ searchParams }: PageProps<"/studio/adjudications/new">) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Apply a rubric correction to earlier work</h1>
      <Suspense fallback={<SkeletonLines lines={4} label="Loading the rubric" />}>
        {searchParams.then((sp) => (
          <Body rubric={typeof sp.rubric === "string" ? sp.rubric : ""} />
        ))}
      </Suspense>
    </div>
  );
}

async function Body({ rubric }: { rubric: string }) {
  let auth;
  try {
    auth = await requireStaff(`/studio/adjudications/new?rubric=${rubric}`);
  } catch (e) {
    if (e instanceof StudioForbiddenError) return <Notice tone="warn" title="Staff only">{e.message}</Notice>;
    throw e;
  }
  if (!/^[0-9a-f-]{36}$/i.test(rubric)) notFound();
  const item = await getItem(auth.token, rubric);
  if (!item || item.kind !== "rubric") notFound();
  const res = await api<AdjudicationSources>(`/v1/studio/written/adjudication-sources?rubric_item_id=${rubric}`, { token: auth.token });
  if (!res.ok) notFound();
  const src = res.data;
  return (
    <div className="space-y-4">
      <p>
        Rubric <span className="font-medium">{item.title}</span>: the corrected, published version is {src.published_number ?? "—"}.
      </p>
      <Notice title="What happens">
        Only submitted scripts are affected; tests still being written keep the rubric they started with and are corrected when submitted. Marks carry
        forward unchanged only where the scoring basis is identical; other marked questions go to an independent teacher to re-mark, and unmarked or
        pending questions will be marked with the corrected rubric. Released results stay as they are until then, and every affected learner is told
        once. Nothing is charged. Applying needs a multi-factor sign-in.
      </Notice>
      {src.versions.length === 0 ? (
        <Notice tone="warn" title="Nothing to correct">This rubric has no earlier published version for the same question.</Notice>
      ) : (
        <NewAdjudicationForm rubricId={item.id} sources={src} />
      )}
    </div>
  );
}
