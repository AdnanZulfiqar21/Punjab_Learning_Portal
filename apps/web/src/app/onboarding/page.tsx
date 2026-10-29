import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { CenteredCard } from "@/components/learner-pages";
import { SkeletonLines } from "@/components/ui";
import { currentUser } from "@/lib/session";
import { OnboardingForm } from "./onboarding-form";

export const metadata: Metadata = { title: "Set up", robots: { index: false } };

export default function OnboardingPage() {
  return (
    <CenteredCard
      icon="graduation-cap"
      width="2xl"
      title="Set up your learning"
      lead="You can change any of this later. We never ask for CNIC or other identity documents."
    >
      <Suspense fallback={<SkeletonLines lines={6} label="Loading your preferences" />}>
        <Form />
      </Suspense>
    </CenteredCard>
  );
}

async function Form() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/onboarding");
  return <OnboardingForm profile={user.me.profile} />;
}
