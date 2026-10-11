import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { Lecture, NarrationVoice, StudioItemSummary } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { LANGUAGE, STATUS } from "./labels";
import { ProposeVoice, StartLecture, VoiceDecision } from "./lecture-forms";

export const metadata: Metadata = { title: "Lectures", robots: { index: false } };


// P07.S4.T3 (LECTURE-01): premium animated lectures as traceable production records. Nothing here reaches learners
// until the media provider exists (B05); "academically approved" only ever comes from an independent review.
export default function LecturesPage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { label: "Lectures" }]} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Lectures</h1>
        <p className="text-muted">
          Each lecture follows a reviewed storyboard, is narrated by an approved voice, and is approved only by an independent subject
          reviewer. Learners can&apos;t watch lectures yet: that needs the video provider.
        </p>
      </div>
      <Suspense fallback={<SkeletonLines lines={6} label="Loading lectures" />}>
        <Board />
      </Suspense>
    </div>
  );
}

async function Board() {
  const user = await currentUser();
  if (!user) redirect("/signin?next=/studio/lectures");
  const owner = user.me.roles.includes("owner_admin");
  const author = user.me.roles.includes("content_author");
  const [voices, lectures, storyboards] = await Promise.all([
    api<NarrationVoice[]>("/v1/studio/voices", { token: user.token }),
    api<Lecture[]>("/v1/studio/lectures", { token: user.token }),
    api<StudioItemSummary[]>("/v1/studio/queue?kind=storyboard&state=published", { token: user.token }),
  ]);
  if (!voices.ok) return <Notice tone="warn" title="Couldn't load lectures">{voices.problem?.detail ?? "Please try again."}</Notice>;
  const approved = voices.data.filter((v) => v.status === "approved");
  return (
    <div className="space-y-8">
      <section aria-labelledby="voices-h" className="space-y-3">
        <h2 id="voices-h" className="text-lg font-semibold">
          Narration voices
        </h2>
        {voices.data.length === 0 ? (
          <p className="text-sm text-muted">No voices yet. Propose one; the owner approves it before any lecture can use it.</p>
        ) : (
          <ul className="space-y-2">
            {voices.data.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
                <span className="font-medium">{v.name}</span>
                <Badge>{LANGUAGE[v.language] ?? v.language}</Badge>
                <Badge tone={v.status === "approved" ? "ok" : v.status === "retired" ? "info" : "warn"}>{v.status}</Badge>
                <span className="text-muted">
                  {v.tool} · {v.voice_ref}
                </span>
                {owner && v.status !== "retired" && <VoiceDecision id={v.id} status={v.status} />}
              </li>
            ))}
          </ul>
        )}
        {author && <ProposeVoice />}
      </section>

      {lectures.ok || lectures.status !== 403 ? (
        <section aria-labelledby="lectures-h" className="space-y-3">
          <h2 id="lectures-h" className="text-lg font-semibold">
            Lectures
          </h2>
          {author && storyboards.ok && <StartLecture storyboards={storyboards.data.map((s) => ({ id: s.id, title: s.title }))} voices={approved.map((v) => ({ id: v.id, name: v.name, language: v.language }))} />}
          {!lectures.ok ? (
            <Notice tone="warn" title="Couldn't load lectures">
              {lectures.problem?.detail ?? "Please try again."}
            </Notice>
          ) : lectures.data.length === 0 ? (
            <p className="text-sm text-muted">No lectures yet.</p>
          ) : (
            <ul className="space-y-2">
              {lectures.data.map((l) => (
                <li key={l.id} className="rounded-lg border border-border bg-surface px-3 py-2">
                  <Link href={`/studio/lectures/${l.id}`} className="font-medium text-accent underline underline-offset-2">
                    {l.title}
                  </Link>
                  <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
                    {GRADE_LABEL[l.grade]} {SUBJECTS.find(([c]) => c === l.subject)?.[1] ?? l.subject} · {LANGUAGE[l.narration_language]} · {l.voice.name}
                    <Badge tone={l.status === "approved" ? "ok" : l.status === "changes_requested" ? "warn" : "info"}>{STATUS[l.status]}</Badge>
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </div>
  );
}
