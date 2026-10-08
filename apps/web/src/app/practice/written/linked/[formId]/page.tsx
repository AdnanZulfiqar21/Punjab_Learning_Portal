import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import type { LinkedForm } from "@portal/contracts";
import { startLinkedPractice } from "@/app/actions/written";
import { Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "New practice test", robots: { index: false } };

const REASON: Record<string, string> = {
  REWRITE: "You asked to answer these questions again after seeing your feedback.",
  NEW_CONTENT: "A teacher found new or changed work in the copy you sent, so it can only be marked as a new test.",
  INDETERMINATE: "A teacher couldn't tell whether your copy showed the same work, so you can answer again as a new test.",
};

export default function LinkedPracticePage({ params, searchParams }: PageProps<"/practice/written/linked/[formId]">) {
  return (
    <Suspense fallback={<SkeletonLines lines={5} label="Loading your new practice test" />}>
      {Promise.all([params, searchParams]).then(([{ formId }, sp]) => (
        <Confirm formId={formId} failed={typeof sp.error === "string"} />
      ))}
    </Suspense>
  );
}

async function Confirm({ formId, failed }: { formId: string; failed: boolean }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/practice/written/linked/${formId}`);
  if (!/^[0-9a-f-]{36}$/i.test(formId)) notFound();
  const res = await api<LinkedForm>(`/v1/written/linked-forms/${formId}`, { token: user.token });
  if (!res.ok) notFound();
  const f = res.data;
  if (f.started_attempt_id) redirect(`/practice/written/${f.started_attempt_id}`);
  const enough = f.allowance_available >= f.allowance_units;
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">New practice test</h1>
      <p>{REASON[f.linked_from.reason]}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted">Questions</dt>
        <dd>
          {f.question_count} (question {f.linked_from.positions.join(", ")} of{" "}
          <Link className="text-accent underline" href={`/practice/written/${f.linked_from.attempt_id}`}>
            your earlier test
          </Link>
          )
        </dd>
        <dt className="text-muted">Allowance used when you start</dt>
        <dd>
          {f.allowance_units} unit{f.allowance_units === 1 ? "" : "s"} (you have {f.allowance_available})
        </dd>
      </dl>
      <Notice title="Your earlier result stays as it is">
        This is a separate test with its own marks. It doesn&apos;t replace or change the marks on your earlier test, and it isn&apos;t a recheck.
      </Notice>
      {failed && (
        <Notice tone="danger" title="The test couldn't be started">
          Your plan, allowance or teacher marking capacity didn&apos;t allow it just now. Nothing was charged; try again later.
        </Notice>
      )}
      {enough ? (
        <form action={startLinkedPractice.bind(null, f.form_id)}>
          <button
            type="submit"
            className="rounded-lg bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
          >
            Start the new test
          </button>
        </form>
      ) : (
        <Notice tone="warn" title="Not enough written allowance">
          Starting this test needs {f.allowance_units} unit{f.allowance_units === 1 ? "" : "s"}. <Link href="/account" className="underline">See your plan</Link>.
        </Notice>
      )}
    </div>
  );
}
