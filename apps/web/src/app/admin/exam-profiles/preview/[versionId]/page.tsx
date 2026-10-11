import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { api, currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Sample form preview", robots: { index: false } };

type Block = { type: string; [key: string]: unknown };
type Item = {
  position: number;
  section: string;
  item_id: string;
  learner: { stem: Block[]; options: { id: string; blocks: Block[] }[] };
  oldest_client: { stem: Block[]; options: { id: string; blocks: Block[] }[]; fallback_blocks: number };
  checks: string[];
};
type Preview = { version: number; status: string; seed: number; shortages: { subject: string; required: number; available?: number }[]; items: Item[] };
type Answers = { answers: { position: number; correct_option_id: string; explanation: { correct?: Block[] } }[] };

// P09.S4.T1 (FORM-PREVIEW-01): what a learner would get from this pattern version, before it is verified or published.
export default function PreviewPage({ params, searchParams }: PageProps<"/admin/exam-profiles/preview/[versionId]">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/admin/exam-profiles", label: "Exam profiles" }, { label: "Sample form" }]} />
      <Suspense fallback={<SkeletonLines lines={6} label="Building a sample form" />}>
        {Promise.all([params, searchParams]).then(([p, sp]) => (
          <Sample versionId={p.versionId} seed={typeof sp.seed === "string" ? sp.seed : undefined} withAnswers={sp.answers === "1"} />
        ))}
      </Suspense>
    </div>
  );
}

async function Sample({ versionId, seed, withAnswers }: { versionId: string; seed?: string; withAnswers: boolean }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/admin/exam-profiles/preview/${versionId}`);
  const base = `/v1/admin/exam-profile-versions/${encodeURIComponent(versionId)}/preview`;
  const res = await api<Preview>(`${base}${seed && /^\d+$/.test(seed) ? `?seed=${seed}` : ""}`, { token: user.token });
  if (!res.ok) {
    return (
      <Notice tone="warn" title={res.status === 403 ? "Multi-factor sign-in needed" : "Couldn't build a sample"}>
        {res.problem?.detail ?? "Please try again."}
      </Notice>
    );
  }
  const p = res.data;
  const keys = withAnswers ? await api<Answers>(`${base}/answers?seed=${p.seed}`, { token: user.token }) : null;
  const answers = keys?.ok ? new Map(keys.data.answers.map((a) => [a.position, a])) : null;
  const here = `/admin/exam-profiles/preview/${versionId}`;
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Sample form · version {p.version}</h1>
        <p className="text-sm text-muted">
          {p.status} version · sample {p.seed} · nothing is saved. The same sample number always shows the same questions.
        </p>
        <p className="flex flex-wrap gap-3 text-sm">
          <Link href={here} className="text-accent underline underline-offset-2">
            Another sample
          </Link>
          {answers ? (
            <Link href={`${here}?seed=${p.seed}`} className="text-accent underline underline-offset-2">
              Hide answers
            </Link>
          ) : (
            <Link href={`${here}?seed=${p.seed}&answers=1`} className="text-accent underline underline-offset-2">
              Show the answer report
            </Link>
          )}
        </p>
      </div>
      {p.shortages.length > 0 && (
        <Notice tone="warn" title="Not enough approved questions for this pattern">
          {p.shortages.map((s) => `${s.subject}: ${s.available ?? "?"} of ${s.required}`).join(" · ")}
        </Notice>
      )}
      <ol className="space-y-4">
        {p.items.map((it) => {
          const a = answers?.get(it.position);
          return (
            <li key={it.position} className="space-y-3 rounded-xl border border-border bg-surface p-4">
              <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
                <span className="font-medium text-foreground">Question {it.position}</span> {it.section}
                {it.oldest_client.fallback_blocks > 0 && <Badge tone="info">{it.oldest_client.fallback_blocks} fallback block(s) on the oldest client</Badge>}
              </p>
              <LessonBlocks blocks={it.learner.stem} headingOffset={1} />
              <ul className="space-y-2">
                {it.learner.options.map((o) => (
                  <li key={o.id} className={`rounded-lg border px-3 py-2 ${a?.correct_option_id === o.id ? "border-ok bg-ok-soft" : "border-border"}`}>
                    <LessonBlocks blocks={o.blocks} headingOffset={1} />
                  </li>
                ))}
              </ul>
              {it.checks.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-sm text-warn" aria-label="Checks">
                  {it.checks.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              )}
              {a?.explanation.correct && (
                <div className="rounded-lg border border-border bg-surface-muted p-3 text-sm">
                  <LessonBlocks blocks={a.explanation.correct} headingOffset={1} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
