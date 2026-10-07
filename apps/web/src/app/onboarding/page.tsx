import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { SkeletonLines } from "@/components/ui";
import { currentUser } from "@/lib/session";
import { OnboardingForm } from "./onboarding-form";

export const metadata: Metadata = { title: "Set up", robots: { index: false } };

export default function OnboardingPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Set up your learning</h1>
        <p className="text-muted">You can change any of this later. We never ask for CNIC or other identity documents.</p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your preferences" />}>
        <Form />
      </Suspense>
    </div>
  );
}

async function Form() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/onboarding");
  return <OnboardingForm profile={user.me.profile} />;
}
