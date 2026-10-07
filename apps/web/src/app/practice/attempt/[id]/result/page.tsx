import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import type { ItemReview } from "@portal/contracts";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Notice, SkeletonLines } from "@/components/ui";
import { getResult } from "@/lib/practice";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Practice result", robots: { index: false } };

type Blocks = { type: string }[];

export default function ResultPage({ params }: PageProps<"/practice/attempt/[id]/result">) {
  return (
    <Suspense fallback={<SkeletonLines lines={8} label="Loading your result" />}>
      {params.then(({ id }) => (
        <Result id={id} />
      ))}
    </Suspense>
  );
}

async function Result({ id }: { id: string }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/practice/attempt/${id}/result`);
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  const result = await getResult(user.token, id);
  if (result === null) notFound();
  if (result === "pending") {
    return (
      <Notice title="Not submitted yet">
        <Link href={`/practice/attempt/${id}`} className="underline">
          Return to the test
        </Link>{" "}
        to finish it.
      </Notice>
    );
  }
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Your result</h1>
        {result.status === "not_scorable" ? (
          <Notice tone="warn" title="This test can't be scored">
            Every question was withdrawn after review, so there is nothing to score.
          </Notice>
        ) : (
          <p className="text-lg">
            <span className="text-3xl font-semibold tabular-nums">{result.raw}</span> / {result.maximum}
            {result.percentage !== null && <span className="ml-2 text-muted">({String(result.percentage)}%)</span>}
          </p>
        )}
        <p className="text-sm text-muted">
          {result.answered} of {result.question_count} answered · {result.finalise_reason === "expiry" ? "submitted when time ran out" : "submitted by you"}
        </p>
      </div>
      <ol className="space-y-4">
        {result.items.map((it) => (
          <ReviewItem key={it.position} item={it} />
        ))}
      </ol>
      <Link href="/practice" className="inline-block rounded-lg border border-border bg-surface px-4 py-2 hover:border-accent">
        Practise again
      </Link>
    </div>
  );
}

function ReviewItem({ item }: { item: ItemReview }) {
  const explanation = item.explanation as { correct?: Blocks; distractors?: Record<string, string>; worked_steps?: Blocks };
  return (
    <li className="space-y-3 rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">Question {item.position}</h2>
        {item.treatment !== "NONE" ? (
          <Badge tone="warn">{item.treatment === "EXCLUDE" ? "Excluded after review" : item.treatment === "CREDIT_ALL" ? "Credited to everyone" : "Key corrected"}</Badge>
        ) : item.chosen === null ? (
          <Badge>Not answered</Badge>
        ) : item.correct ? (
          <Badge tone="ok">Correct</Badge>
        ) : (
          <Badge tone="danger">Incorrect</Badge>
        )}
      </div>
      <LessonBlocks blocks={item.stem as Blocks} headingOffset={2} />
      <ul className="space-y-2">
        {item.options.map((o, i) => {
          const isKey = o.id === item.correct_option_id;
          const isChosen = o.id === item.chosen;
          return (
            <li key={o.id} className={`rounded-lg border px-3 py-2 ${isKey ? "border-ok bg-ok-soft" : isChosen ? "border-danger bg-danger-soft" : "border-border"}`}>
              <span className="mr-2 font-medium text-muted">{String.fromCharCode(65 + i)}</span>
              {isKey && <span className="mr-2 text-xs font-semibold text-ok">Correct answer</span>}
              {isChosen && !isKey && <span className="mr-2 text-xs font-semibold text-danger">Your answer</span>}
              <LessonBlocks blocks={o.blocks as Blocks} headingOffset={3} />
              {isChosen && !isKey && explanation.distractors?.[o.id] && <p className="mt-1 text-sm">{explanation.distractors[o.id]}</p>}
            </li>
          );
        })}
      </ul>
      {(explanation.correct?.length ?? 0) > 0 && (
        <div className="rounded-lg bg-surface-muted p-3 text-sm">
          <p className="font-semibold">Why</p>
          <LessonBlocks blocks={explanation.correct ?? []} headingOffset={3} />
          {(explanation.worked_steps?.length ?? 0) > 0 && <LessonBlocks blocks={explanation.worked_steps ?? []} headingOffset={3} />}
        </div>
      )}
    </li>
  );
}
