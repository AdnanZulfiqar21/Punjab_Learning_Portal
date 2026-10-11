import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import type { Lecture } from "@portal/contracts";
import { Badge, Breadcrumbs, Notice, SkeletonLines } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { SUBJECTS } from "@/lib/practice";
import { api, currentUser } from "@/lib/session";
import { CHECKS, LANGUAGE, STATUS } from "../labels";
import { CaptionsForm, MarkersEditor, MasterForm, MasterUpload, ReviewForm, SubmitLecture, TranscriptEditor } from "./detail-forms";

type Marker = { scene_id: string; start_s: number; label: string };

export const metadata: Metadata = { title: "Lecture", robots: { index: false } };

export default function LecturePage({ params }: PageProps<"/studio/lectures/[id]">) {
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ href: "/studio", label: "Studio" }, { href: "/studio/lectures", label: "Lectures" }, { label: "Lecture" }]} />
      <Suspense fallback={<SkeletonLines lines={8} label="Loading the lecture" />}>{params.then((p) => <Detail id={p.id} />)}</Suspense>
    </div>
  );
}

async function Detail({ id }: { id: string }) {
  const user = await currentUser();
  if (!user) redirect(`/signin?next=/studio/lectures/${id}`);
  const res = await api<Lecture>(`/v1/studio/lectures/${encodeURIComponent(id)}`, { token: user.token });
  if (!res.ok) return <Notice tone="warn" title="Lecture not available">{res.problem?.detail ?? "Please try again."}</Notice>;
  const l = res.data;
  const editable = l.status === "in_production" || l.status === "changes_requested";
  const author = user.me.roles.includes("content_author");
  const reviewer = user.me.roles.includes("subject_reviewer");
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{l.title}</h1>
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
          {GRADE_LABEL[l.grade]} {SUBJECTS.find(([c]) => c === l.subject)?.[1] ?? l.subject} · storyboard version {l.storyboard_version} · {LANGUAGE[l.narration_language]} narration by {l.voice.name}
          <Badge tone={l.status === "approved" ? "ok" : l.status === "changes_requested" ? "warn" : "info"}>{STATUS[l.status]}</Badge>
        </p>
        <p className="text-sm">
          {l.academically_approved
            ? "Academically approved by an independent subject reviewer. Learner playback waits on the video provider."
            : "Not academically approved."}
        </p>
      </div>

      {editable && l.missing.length > 0 && (
        <Notice tone="warn" title="Before review">
          <ul className="list-disc pl-5">
            {l.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </Notice>
      )}

      <section aria-labelledby="master-h" className="space-y-2">
        <h2 id="master-h" className="text-lg font-semibold">
          Master video
        </h2>
        {l.master ? (
          <p className="text-sm">
            {String(l.master.filename)} · {Math.round(Number(l.master.bytes) / (1024 * 1024))} MB · {String(l.master.duration_s)} s ·{" "}
            <span className="font-mono text-xs">{String(l.master.sha256)}</span> · {String(l.master.location)}
          </p>
        ) : (
          <p className="text-sm text-muted">Not registered yet.</p>
        )}
        {editable && author && (
          <>
            <MasterUpload id={l.id} />
            <details className="text-sm">
              <summary className="cursor-pointer text-accent">Or register a master kept elsewhere</summary>
              <div className="mt-2">
                <MasterForm id={l.id} />
              </div>
            </details>
          </>
        )}
      </section>

      {l.master && (
        <section aria-labelledby="markers-h" className="space-y-2">
          <h2 id="markers-h" className="text-lg font-semibold">
            Chapter markers
          </h2>
          <p className="text-sm text-muted">Where each storyboard scene starts in the master video. Learners use these to jump between concepts.</p>
          {l.markers && !l.markers_current && (
            <p role="alert" className="rounded-lg border border-warn bg-warn-soft px-3 py-2 text-sm">
              The master video changed since these markers were set. Check each time against the new video and save again.
            </p>
          )}
          <MarkersEditor
            key={String(l.master.sha256)}
            id={l.id}
            initial={((l.markers?.scenes as Marker[] | undefined) ?? (l.marker_proposal as Marker[])).map((m) => ({ ...m }))}
            editable={editable && author}
          />
        </section>
      )}

      <section aria-labelledby="captions-h" className="space-y-2">
        <h2 id="captions-h" className="text-lg font-semibold">
          Captions
        </h2>
        {Object.keys(l.captions).length === 0 ? (
          <p className="text-sm text-muted">None attached.</p>
        ) : (
          <ul className="text-sm">
            {Object.entries(l.captions).map(([lang, vid]) => (
              <li key={lang}>
                {LANGUAGE[lang] ?? lang}:{" "}
                <a href={`/studio/assets/file/${vid}?copy=delivery`} className="font-mono text-xs text-accent underline">
                  {vid}
                </a>
              </li>
            ))}
          </ul>
        )}
        {editable && author && <CaptionsForm id={l.id} language={l.narration_language} />}
      </section>

      <section aria-labelledby="transcript-h" className="space-y-2">
        <h2 id="transcript-h" className="text-lg font-semibold">
          Transcript
        </h2>
        <TranscriptEditor id={l.id} scenes={l.transcript as { scene_id: string; text: string }[]} editable={editable && author} />
      </section>

      {editable && author && <SubmitLecture id={l.id} ready={l.missing.length === 0} />}

      {l.review && (
        <section aria-labelledby="review-h" className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
          <h2 id="review-h" className="text-lg font-semibold">
            Review: {l.review.decision === "approve" ? "approved" : "changes requested"}
          </h2>
          <ul className="space-y-1">
            {CHECKS.map(([k, label]) => (
              <li key={k}>
                {(l.review!.checklist as Record<string, boolean>)[k] ? "✓" : "✗"} {label}
              </li>
            ))}
          </ul>
          <p className="whitespace-pre-line">{String(l.review.notes)}</p>
        </section>
      )}
      {l.status === "in_review" && reviewer && <ReviewForm id={l.id} />}
    </div>
  );
}
