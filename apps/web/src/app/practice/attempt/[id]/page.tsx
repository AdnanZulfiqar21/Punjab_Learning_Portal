import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import { MockRunningNotice } from "@/components/mock-running";
import { buttonClasses } from "@/components/button";
import { Icon } from "@/components/icons";
import { Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
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
  if ("mockRunning" in attempt) {
    return (
      <div className="mx-auto max-w-2xl">
        <MockRunningNotice attemptId={attempt.mockRunning} />
      </div>
    );
  }
  if (attempt.status !== "active") {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { label: "Test submitted" }]} />
          <div className="glass rounded-card px-6 py-6 sm:px-8">
            <p className="text-xs font-semibold tracking-[0.15em] text-accent uppercase">Practice test</p>
            <h1 className="mt-2 font-display text-[28px] leading-9 font-bold tracking-tight sm:text-[36px] sm:leading-[2.75rem]">Test submitted</h1>
          </div>
        </div>
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
        <Link href={`/practice/attempt/${id}/result`} className={buttonClasses({ size: "lg" })}>
          See your result
          <Icon name="arrow-right" size={18} />
        </Link>
      </div>
    );
  }
  // Remount when the server state changes so the runner never works from a stale snapshot.
  return <AttemptRunner key={`${attempt.id}:${attempt.status}`} attempt={attempt} />;
}
