import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import { Notice, SkeletonLines } from "@/components/ui";
import { getAttempt } from "@/lib/practice";
import { currentUser } from "@/lib/session";
import { AttemptRunner } from "./attempt-runner";

export const metadata: Metadata = { title: "Practice test", robots: { index: false } };

export default function AttemptPage({ params }: PageProps<"/practice/attempt/[id]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading your test" />}>
      {params.then(({ id }) => (
        <Attempt id={id} />
      ))}
    </Suspense>
  );
}

async function Attempt({ id }: { id: string }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/practice/attempt/${id}`);
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const attempt = await getAttempt(user.token, id);
  if (!attempt) notFound();
  if (attempt.status !== "active") {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Test submitted</h1>
        <Notice tone="ok" title={attempt.receipt?.reason === "expiry" ? "Time is up" : "Submitted"}>
          {attempt.receipt
            ? `${attempt.receipt.answered_count} of ${attempt.receipt.question_count} questions answered. Receipt ${attempt.receipt.id.slice(0, 8)}.`
            : "Your answers are saved."}
        </Notice>
        {(attempt.not_counted ?? []).length > 0 && (
          <Notice tone="warn" title="Some last changes weren't counted">
            {(attempt.not_counted ?? []).length === 1 ? "Question" : "Questions"} {(attempt.not_counted ?? []).map((n) => n.position).join(", ")}:
            your last change {(attempt.not_counted ?? []).length === 1 ? "wasn't" : "to each wasn't"} counted. The answer you had saved
            before it, if any, was marked. Your result explains why.
          </Notice>
        )}
        <Link href={`/practice/attempt/${id}/result`} className="inline-block rounded-lg bg-accent px-4 py-2.5 font-medium text-white dark:text-background">
          See your result
        </Link>
      </div>
    );
  }
  // Remount when the server state changes so the runner never works from a stale snapshot.
  return <AttemptRunner key={`${attempt.id}:${attempt.status}`} attempt={attempt} />;
}
