import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";
import type { AttemptResult, ItemReview } from "@portal/contracts";
import { LessonBlocks } from "@/components/lesson-blocks";
import { typesetEquations } from "@/lib/typeset";
import { buttonClasses } from "@/components/button";
import { GlassCard } from "@/components/glass-card";
import { ProgressBar } from "@/components/progress-bar";
import { SectionHeader } from "@/components/section-header";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { MockRunningNotice } from "@/components/mock-running";
import { getResult } from "@/lib/practice";
import { currentUser } from "@/lib/session";
import { TIME_ZONE } from "@/lib/dates";

// P11.S3.T3 (RECEIPT-01): why a learner's latest change to a question wasn't counted.
const NOT_COUNTED: Record<string, string> = {
  late: "arrived after the time was up",
  finalised: "arrived after the test was submitted",
  invalid: "wasn't a valid option",
};

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
  if (typeof result === "object" && "mockRunning" in result) return <MockRunningNotice attemptId={result.mockRunning} />;
  if (typeof result === "object" && "heldUntil" in result) {
    return (
      <Notice title="Your answers are saved">
        {result.heldUntil
          ? `Results for this scheduled mock are released on ${new Date(result.heldUntil).toLocaleString("en-GB", { dateStyle: "full", timeStyle: "short", timeZone: TIME_ZONE })}. Come back then.`
          : "Results for this scheduled mock aren't released yet. Come back later."}
      </Notice>
    );
  }
  if (result === "scoring") {
    return (
      <Notice title="Submitted: your result is being prepared">
        Your answers are saved and your test is submitted. The result will appear here shortly; you don&apos;t need to do anything.
      </Notice>
    );
  }
  if (result === "pending") {
    return (
      <Notice title="Not submitted yet">
        <Link href={`/practice/attempt/${id}`} className="font-medium text-accent underline underline-offset-2">
          Return to the test
        </Link>{" "}
        to finish it.
      </Notice>
    );
  }
  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <Breadcrumbs items={[{ href: "/practice", label: "Practice" }, { href: "/practice/progress", label: "Progress report" }, { label: "Your result" }]} />
        <GlassCard className="space-y-3 sm:px-8 sm:py-7">
        <p className="text-xs font-semibold tracking-[0.15em] text-accent uppercase">Practice</p>
        <h1 className="font-display text-[28px] leading-9 font-bold tracking-tight sm:text-[36px] sm:leading-[2.75rem]">Your result</h1>
        {result.status === "not_scorable" ? (
          <Notice tone="warn" title="This test can't be scored">
            Every question was withdrawn after review, so there is nothing to score.
          </Notice>
        ) : (
          <>
            <p className="text-lg">
              <span className="font-display text-5xl font-bold tabular-nums">{result.raw}</span> / {result.maximum}
              {result.percentage !== null && <span className="ml-2 text-muted">({String(result.percentage)}%)</span>}
            </p>
            {result.maximum > 0 && (
              <ProgressBar value={result.raw} max={result.maximum} label="Your score" valueText={`${result.raw} of ${result.maximum}`} className="h-2 max-w-md" />
            )}
          </>
        )}
        {result.revised_at && (
          <Notice title={`Updated ${new Date(result.revised_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE })}`}>
            {result.revision_reason} Your earlier result stays in your history.
          </Notice>
        )}
        </GlassCard>
        <p className="text-sm text-muted">
          {result.answered} of {result.question_count} answered · {result.finalise_reason === "expiry" ? "submitted when time ran out" : "submitted by you"}
          {result.timing?.seconds_used != null && ` · ${Math.max(1, Math.round(result.timing.seconds_used / 60))} min`}
          {result.form?.profile && ` · pattern ${result.form.profile} v${result.form.profile_version}`}
          {(result.counts?.excluded ?? 0) > 0 && ` · ${result.counts?.excluded} withdrawn after review`}
          {(result.counts?.credited ?? 0) > 0 && ` · ${result.counts?.credited} credited to everyone`}
        </p>
        {(result.not_counted ?? []).length > 0 && (
          <Notice tone="warn" title="Some last changes weren't counted">
            <ul className="list-disc pl-5">
              {(result.not_counted ?? []).map((n) => (
                <li key={n.position}>
                  Question {n.position}: your last change {NOT_COUNTED[n.reason]}. The answer you had saved before it, if any, was marked.
                </li>
              ))}
            </ul>
          </Notice>
        )}
        {(result.sections ?? []).length > 1 && (
          <ul className="flex flex-wrap gap-2 text-sm" aria-label="Sections">
            {(result.sections ?? []).map((s) => (
              <li key={s.from_position} className="glass rounded-full px-3.5 py-1.5 font-medium shadow-none">
                {s.label}: {s.raw} / {s.maximum}
              </li>
            ))}
          </ul>
        )}
        {result.comparison && <Comparison c={result.comparison} />}
        {(result.history ?? []).length > 1 && (
          <details className="text-sm">
            <summary className="flex min-h-11 cursor-pointer items-center text-muted">Score history ({(result.history ?? []).length} versions)</summary>
            <ol className="mt-1 space-y-1">
              {(result.history ?? []).map((h) => (
                <li key={h.version}>
                  v{h.version}: {h.raw} / {h.maximum} · {new Date(h.created_at).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE })} · {h.reason}
                </li>
              ))}
            </ol>
          </details>
        )}
      </div>
      <section aria-labelledby="review-h">
        <SectionHeader id="review-h" title="Question by question" />
        <ol className="space-y-4">
          {result.items.map((it) => (
            <ReviewItem key={it.position} item={it} attemptId={id} />
          ))}
        </ol>
      </section>
      <Link href="/practice" className={buttonClasses({ variant: "secondary", size: "lg" })}>
        Practise again
      </Link>
    </div>
  );
}

// P12.S2.T3 (COMPARISON-01): scheduled sessions' fixed forms only; the API decides whether a percentile may be shown.
function Comparison({ c }: { c: NonNullable<AttemptResult["comparison"]> }) {
  const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: TIME_ZONE });
  return (
    <section aria-labelledby="compare" className="glass space-y-1 rounded-card p-5 text-sm">
      <h2 id="compare" className="font-display text-lg font-semibold">
        How you compare
      </h2>
      {c.state === "published" && c.percentile != null ? (
        <>
          <p>
            <span className="text-2xl font-semibold tabular-nums">{String(c.percentile)}</span> percentile
          </p>
          <p>{c.message}</p>
          {c.window_start && c.window_end && (
            <p className="text-muted">
              Results finalised {day(c.window_start)} to {day(c.window_end)} · comparison v{c.version}
            </p>
          )}
          <p className="text-muted">{c.tie_rule}</p>
        </>
      ) : (
        <p>{c.message}</p>
      )}
      {c.state !== "not_included" && <p className="text-muted">{c.group}</p>}
      <p className="text-muted">{c.limits}</p>
    </section>
  );
}

function ReviewItem({ item, attemptId }: { item: ItemReview; attemptId: string }) {
  const assetUrl = (v: string) => `/practice/attempt/${attemptId}/assets/${v}`; // QUESTION-DIAGRAMS-01
  const explanation = item.explanation as { correct?: Blocks; distractors?: Record<string, string>; worked_steps?: Blocks };
  return (
    // The question, options and explanation are read on a solid surface (owner rule 5).
    <li className="space-y-3 rounded-card border border-border bg-surface p-5 shadow-glass sm:p-6">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-display text-lg font-semibold">Question {item.position}</h3>
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
      {item.passage && (
        <section aria-label="Passage" className="rounded-inner border border-border bg-surface-muted px-4 py-3">
          <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">Passage</p>
          <LessonBlocks blocks={item.passage.blocks as Blocks} typeset={typesetEquations(item.passage.blocks as Blocks)} headingOffset={3} assetUrl={assetUrl} />
        </section>
      )}
      <LessonBlocks blocks={item.stem as Blocks} typeset={typesetEquations(item.stem as Blocks)} headingOffset={2} assetUrl={assetUrl} />
      <ul className="space-y-2">
        {item.options.map((o, i) => {
          const isKey = o.id === item.correct_option_id;
          const isChosen = o.id === item.chosen;
          return (
            <li key={o.id} className={`rounded-inner border px-4 py-2.5 break-words ${isKey ? "border-ok bg-ok-soft" : isChosen ? "border-danger bg-danger-soft" : "border-border"}`}>
              <span className="mr-2 font-medium text-muted">{String.fromCharCode(65 + i)}</span>
              {isKey && <span className="mr-2 text-xs font-semibold text-ok">Correct answer</span>}
              {isChosen && !isKey && <span className="mr-2 text-xs font-semibold text-danger">Your answer</span>}
              <LessonBlocks blocks={o.blocks as Blocks} typeset={typesetEquations(o.blocks as Blocks)} headingOffset={3} assetUrl={assetUrl} />
              {isChosen && !isKey && explanation.distractors?.[o.id] && <p className="mt-1 text-sm">{explanation.distractors[o.id]}</p>}
            </li>
          );
        })}
      </ul>
      {(explanation.correct?.length ?? 0) > 0 && (
        <div className="rounded-inner bg-surface-muted p-4 text-sm">
          <p className="font-semibold">Why</p>
          <LessonBlocks blocks={explanation.correct ?? []} typeset={typesetEquations(explanation.correct)} headingOffset={3} assetUrl={assetUrl} />
          {(explanation.worked_steps?.length ?? 0) > 0 && <LessonBlocks blocks={explanation.worked_steps ?? []} headingOffset={3} assetUrl={assetUrl} />}
        </div>
      )}
      {(item.related_lessons ?? []).length > 0 && (
        <p className="text-sm">
          Revise:{" "}
          {(item.related_lessons ?? []).map((l, i) => (
            <span key={l.id}>
              {i > 0 && " · "}
              <Link href={`/learn/chapter/${l.chapter_id}#lesson-${l.id}`} className="text-accent underline underline-offset-2">
                {l.title}
              </Link>
            </span>
          ))}
        </p>
      )}
      <Link
        href={`/help/new?category=academic_report&kind=attempt&id=${attemptId}&position=${item.position}`}
        className="inline-flex min-h-11 items-center text-sm text-muted underline underline-offset-2 hover:text-foreground"
      >
        Report a problem with question {item.position}
      </Link>
    </li>
  );
}
