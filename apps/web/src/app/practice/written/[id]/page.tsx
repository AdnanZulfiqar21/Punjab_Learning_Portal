import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import { SkeletonLines } from "@/components/ui";
import { currentUser } from "@/lib/session";
import { getWrittenAttempt } from "@/lib/written";
import { WrittenRunner } from "./written-runner";

export const metadata: Metadata = { title: "Written test", robots: { index: false } };

export default function WrittenAttemptPage({ params }: PageProps<"/practice/written/[id]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading your written test" />}>
      {params.then(({ id }) => (
        <Attempt id={id} />
      ))}
    </Suspense>
  );
}

async function Attempt({ id }: { id: string }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/practice/written/${id}`);
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const attempt = await getWrittenAttempt(user.token, id);
  if (!attempt) notFound();
  return <WrittenRunner key={`${attempt.id}:${attempt.status}:${attempt.manifest_revision}`} attempt={attempt} />;
}
