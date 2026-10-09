import type { Metadata } from "next";
import { Suspense } from "react";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { requireSupportStaff, StudioForbiddenError } from "@/lib/studio";
import { LookupForm } from "./lookup-form";

export const metadata: Metadata = { title: "Find a learner", robots: { index: false } };

export default function FindLearnerPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Breadcrumbs items={[{ href: "/studio/support", label: "Support queue" }, { label: "Find a learner" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Find a learner</h1>
        <p className="text-muted">Exact email only. Every lookup is recorded. Needs a multi-factor sign-in.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={2} label="Loading" />}>
        <Gate />
      </Suspense>
    </div>
  );
}

async function Gate() {
  let isSupport = false;
  try {
    ({ isSupport } = await requireSupportStaff("/studio/support/learners"));
  } catch (e) {
    if (!(e instanceof StudioForbiddenError)) throw e;
  }
  if (!isSupport) return <Notice tone="warn" title="Support staff only">Only support staff can look up learners.</Notice>;
  return <LookupForm />;
}
