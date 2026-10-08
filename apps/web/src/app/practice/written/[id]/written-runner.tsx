"use client";

// Written-script runner (W03/W04). States are kept distinct and honest: a file chosen on this device, uploading,
// uploaded but NOT submitted, and submitted (sealed with a receipt). Nothing is marked until it is submitted.
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { WrittenAttempt, WrittenPage, WrittenResult } from "@portal/contracts";
import { saveMapping, sealScript } from "@/app/actions/written";
import { LessonBlocks } from "@/components/lesson-blocks";
import { PendingAction } from "./pending-action";
import { PractiseAgain } from "./practise-again";
import { RecheckPanel } from "./recheck-panel";
import { Notice } from "@/components/ui";

type Slot = { pages: string[]; unanswered: boolean };
type Upload = { id: string; name: string; progress: number; status: "uploading" | "failed"; error?: string };
const marks = (u: number) => String(u / 100);
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { timeStyle: "short", dateStyle: "medium" });

function uploadFile(attemptId: string, file: File, onProgress: (p: number) => void): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/practice/written/${attemptId}/upload`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page */
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => resolve({ status: 0, body: null });
    xhr.send(file);
  });
}

export function WrittenRunner({ attempt, result = null }: { attempt: WrittenAttempt; result?: WrittenResult | null }) {
  const router = useRouter();
  const [pages, setPages] = useState<WrittenPage[]>(attempt.pages);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [slots, setSlots] = useState<Record<string, Slot>>(() => {
    const out: Record<string, Slot> = {};
    const m = (attempt.manifest as { slots?: Record<string, Slot> }).slots ?? {};
    for (const it of attempt.items) for (const s of it.slots) out[s.key] = m[s.key] ?? { pages: [], unanswered: false };
    return out;
  });
  const [revision, setRevision] = useState(attempt.manifest_revision);
  const [mapState, setMapState] = useState<"saved" | "saving" | "error" | "conflict">("saved");
  const [mapError, setMapError] = useState<string | null>(null);
  const [sealing, setSealing] = useState(false);
  const [sealError, setSealError] = useState<string | null>(null);
  const [now, setNow] = useState<number | null>(null);
  const offset = useRef<number | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savingPromise = useRef<Promise<boolean> | null>(null);
  const revisionRef = useRef(attempt.manifest_revision);
  const active = attempt.status === "active";
  const cutoff = new Date(attempt.upload_cutoff_at).getTime();
  const closed = now !== null && now > cutoff;

  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => {
      offset.current ??= new Date(attempt.server_now).getTime() - Date.now();
      setNow(Date.now() + offset.current);
    }, 1000);
    return () => clearInterval(t);
  }, [active, attempt.server_now]);

  useEffect(() => {
    if (closed) router.refresh(); // the server expires the attempt after U; show its honest state
  }, [closed, router]);

  async function addFiles(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) {
      const tmp = crypto.randomUUID();
      setUploads((u) => [...u, { id: tmp, name: file.name, progress: 0, status: "uploading" }]);
      const res = await uploadFile(attempt.id, file, (p) => setUploads((u) => u.map((x) => (x.id === tmp ? { ...x, progress: p } : x))));
      if (res.status === 201) {
        const body = res.body as { pages: WrittenPage[]; duplicate: boolean; warnings: string[] };
        setUploads((u) => u.filter((x) => x.id !== tmp));
        setPages((p) => [...p, ...body.pages.filter((n) => !p.some((x) => x.id === n.id))]); // a PDF adds one page per PDF page
        setNotes((n) => [...n, ...(body.duplicate ? [`${file.name} was already uploaded.`] : []), ...body.warnings.map((w) => `${file.name}: ${w}`)]);
      } else {
        const detail = (res.body as { detail?: string } | null)?.detail;
        setUploads((u) =>
          u.map((x) => (x.id === tmp ? { ...x, status: "failed", error: detail ?? (res.status === 0 ? "Connection lost. Try again." : `Upload failed (${res.status}).`) } : x)),
        );
      }
    }
  }

  function persistMapping(next: Record<string, Slot>) {
    setSlots(next);
    setMapState("saving");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveTimer.current = null;
      savingPromise.current = (async () => {
        const out = await saveMapping(attempt.id, revisionRef.current, next);
        if (out.kind === "ok") {
          revisionRef.current = out.attempt.manifest_revision;
          setRevision(out.attempt.manifest_revision);
          setMapState("saved");
          setMapError(null);
          return true;
        }
        setMapState(out.kind === "conflict" ? "conflict" : "error");
        setMapError(out.kind === "error" ? [out.message, ...(out.errors ?? [])].join(" ") : out.message);
        return false;
      })();
    }, 600);
  }

  function togglePage(key: string, pageId: string, on: boolean) {
    const cur = slots[key];
    const pagesFor = on ? [...cur.pages, pageId] : cur.pages.filter((p) => p !== pageId);
    persistMapping({ ...slots, [key]: { pages: pagesFor, unanswered: on ? false : cur.unanswered } });
  }

  function toggleUnanswered(key: string, on: boolean) {
    persistMapping({ ...slots, [key]: { pages: on ? [] : slots[key].pages, unanswered: on } });
  }

  async function submit() {
    setSealing(true);
    setSealError(null);
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
      saveTimer.current = null;
      const out = await saveMapping(attempt.id, revisionRef.current, slots);
      if (out.kind !== "ok") {
        setSealing(false);
        setSealError(out.message);
        return;
      }
      revisionRef.current = out.attempt.manifest_revision;
    } else if (savingPromise.current && !(await savingPromise.current)) {
      setSealing(false);
      setSealError("Your answer mapping couldn't be saved. Fix it and try again.");
      return;
    }
    const storageKey = `written-seal:${attempt.id}`;
    let key: string;
    try {
      key = window.localStorage.getItem(storageKey) ?? crypto.randomUUID().replaceAll("-", "");
      window.localStorage.setItem(storageKey, key);
    } catch {
      key = crypto.randomUUID().replaceAll("-", "");
    }
    const out = await sealScript(attempt.id, key, revisionRef.current);
    setSealing(false);
    if (out.kind === "error") {
      setSealError(out.missing?.length ? `${out.message} Missing: ${out.missing.join(", ")}.` : out.message);
      return;
    }
    router.refresh();
  }

  const pageLabel = (id: string) => `Page ${pages.findIndex((p) => p.id === id) + 1}`;
  const complete = Object.values(slots).every((s) => s.pages.length > 0 || s.unanswered);
  const remaining = now === null ? null : Math.max(0, cutoff - now);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{attempt.linked_from ? "New practice test" : "Written test"}</h1>
        {attempt.linked_from && (
          <Notice title="Linked to an earlier test">
            New answers to question {attempt.linked_from.positions.join(", ")} of{" "}
            <a className="text-accent underline" href={`/practice/written/${attempt.linked_from.attempt_id}`}>
              your earlier test
            </a>
            . This test is marked on its own; the earlier result doesn&apos;t change.
          </Notice>
        )}
        {attempt.status === "sealed" && attempt.receipt && (
          <Notice tone="ok" title="Submitted for marking">
            Receipt {attempt.receipt.id.slice(0, 8)} · {attempt.receipt.answered_slots} answered, {attempt.receipt.unanswered_slots} marked not answered ·
            received {when(attempt.receipt.admitted_at)}. A teacher will mark it against the approved rubric.
          </Notice>
        )}
        {attempt.status === "expired" && (
          <Notice tone="warn" title="The upload window closed before you submitted">
            {pages.length} page(s) reached the server but were not submitted, so they won&apos;t be marked. You can start a new practice test.
          </Notice>
        )}
        {active && (
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
            {attempt.writing_deadline_at && (
              <>
                <dt className="text-muted">Stop writing at</dt>
                <dd>{when(attempt.writing_deadline_at)}</dd>
              </>
            )}
            <dt className="text-muted">Upload and submit by</dt>
            <dd>
              {when(attempt.upload_cutoff_at)}
              {remaining !== null && <span className="ml-2 font-mono tabular-nums text-muted">({Math.floor(remaining / 60000)}:{String(Math.floor((remaining % 60000) / 1000)).padStart(2, "0")} left)</span>}
            </dd>
            <dt className="text-muted">Total</dt>
            <dd>{marks(attempt.max_units)} marks</dd>
          </dl>
        )}
      </header>

      {attempt.status === "sealed" && (
        <section aria-labelledby="result-h" className="space-y-3">
          <h2 id="result-h" className="text-lg font-semibold">
            Your marks
          </h2>
          {!result || result.status === "pending" ? (
            <Notice title="Waiting for a teacher">Your script is in the marking queue. Marks appear here once a teacher releases them.</Notice>
          ) : (
            <div className="space-y-3">
              {result.completeness === "complete" ? (
                <p className="text-lg">
                  <span className="text-3xl font-semibold tabular-nums">{marks(result.total_units ?? 0)}</span> / {marks(result.max_units)}
                  <span className="ml-2 text-sm text-muted">
                    {(result.awaiting_regrade ?? []).length > 0
                      ? `marked by a teacher; question ${(result.awaiting_regrade ?? []).join(", ")} is waiting to be re-marked under a corrected marking guide`
                      : result.decision_method === "SYSTEM" && result.history.at(-1)?.case_kind === "regrade"
                        ? "marked by a teacher; carried forward unchanged after a marking-guide correction"
                        : "marked by a teacher"}
                  </span>
                </p>
              ) : (
                <Notice tone="warn" title={result.completeness === "partial_pending" ? "Marking isn't finished yet" : "Some questions couldn't be assessed"}>
                  So far {marks(result.total_units ?? 0)} out of {marks(result.scored_max_units ?? 0)} on the questions a teacher marked. There is no final total until
                  every question is resolved, and nothing is counted as zero just because it wasn&apos;t assessed.
                </Notice>
              )}
              {(result.notices ?? []).map((n) => (
                <Notice key={`${n.kind}:${n.created_at}`} title="Marking guide corrected">
                  {n.message}
                </Notice>
              ))}
              {result.questions.map((q) => (
                <div key={q.position} className="space-y-2 rounded-xl border border-border bg-surface p-4">
                  <p className="font-semibold">
                    Question {q.position}:{" "}
                    {q.status === "scored" ? `${marks(q.earned_units ?? 0)} / ${marks(q.max_units)}` : q.status === "pending" ? "pending" : "couldn't be assessed"}
                  </p>
                  {q.status !== "scored" && (
                    <p className="text-sm text-muted">
                      {q.status_reason}
                      {q.status === "unavailable" && " The allowance for this question was returned to your plan."}
                    </p>
                  )}
                  <PendingAction attemptId={attempt.id} q={q} />
                  <ul className="space-y-1 text-sm">
                    {q.criteria.map((c) => (
                      <li key={c.id}>
                        <span className="font-medium">
                          {marks(c.earned_units)} / {marks(c.max_units)}
                        </span>{" "}
                        {c.description}
                        {c.reason && <span className="block text-muted">{c.reason}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <RecheckPanel attemptId={attempt.id} result={result} marks={marks} />
              <PractiseAgain attemptId={attempt.id} result={result} />
            </div>
          )}
        </section>
      )}

      <section aria-labelledby="questions-h" className="space-y-4">
        <h2 id="questions-h" className="text-lg font-semibold">
          Questions
        </h2>
        {attempt.items.map((it) => (
          <article key={it.position} className="space-y-3 rounded-xl border border-border bg-surface p-5">
            <div className="flex justify-between gap-3">
              <h3 className="font-semibold">Question {it.position}</h3>
              <span className="text-sm text-muted">{marks(it.max_units)} marks</span>
            </div>
            <LessonBlocks blocks={it.stem as { type: string }[]} headingOffset={3} />
            {(it.subparts as { id: string; label: string; blocks: { type: string }[]; max_units: number }[]).map((s) => (
              <div key={s.id} className="flex gap-3">
                <span className="font-medium">{s.label}</span>
                <div className="flex-1">
                  <LessonBlocks blocks={s.blocks} headingOffset={4} />
                </div>
                <span className="text-sm text-muted">[{marks(s.max_units)}]</span>
              </div>
            ))}
          </article>
        ))}
      </section>

      <section aria-labelledby="pages-h" className="space-y-3">
        <h2 id="pages-h" className="text-lg font-semibold">
          Your pages
        </h2>
        {active && (
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 font-medium hover:border-accent">
            <input
              type="file"
              accept="image/jpeg,image/png,application/pdf"
              capture="environment"
              multiple
              className="sr-only"
              onChange={(e) => {
                void addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            Add photos or a PDF
          </label>
        )}
        <ul className="grid gap-3 sm:grid-cols-3" aria-label="Uploaded pages">
          {pages.map((p, i) => (
            <li key={p.id} className="space-y-1 rounded-lg border border-border bg-surface p-2 text-sm">
              {/* eslint-disable-next-line @next/next/no-img-element -- private, uncached preview served by our own route */}
              <img src={`/practice/written/${attempt.id}/pages/${p.id}`} alt={`Page ${i + 1}`} className="h-40 w-full rounded object-contain" />
              <p>
                Page {i + 1} · {attempt.status === "sealed" ? "submitted" : "uploaded, not yet submitted"}
              </p>
              {p.file_pages > 1 && (
                <p className="text-muted">
                  PDF page {p.page_index} of {p.file_pages}
                </p>
              )}
            </li>
          ))}
          {uploads.map((u) => (
            <li key={u.id} className="rounded-lg border border-dashed border-border p-2 text-sm" role="status">
              <p className="truncate">{u.name}</p>
              {u.status === "uploading" ? <progress max={100} value={u.progress} className="w-full" aria-label={`Uploading ${u.name}`} /> : <p className="text-danger">{u.error}</p>}
            </li>
          ))}
        </ul>
        {notes.length > 0 && (
          <ul className="space-y-1 text-sm text-warn">
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </section>

      {active && (
        <section aria-labelledby="map-h" className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 id="map-h" className="text-lg font-semibold">
              Which pages answer which question?
            </h2>
            <span role="status" aria-live="polite" className={`text-sm ${mapState === "error" || mapState === "conflict" ? "text-danger" : "text-muted"}`}>
              {mapState === "saving" ? "Saving…" : mapState === "saved" ? `Saved · revision ${revision}` : mapError}
            </span>
          </div>
          {mapState === "conflict" && (
            <button type="button" onClick={() => router.refresh()} className="text-sm text-accent underline">
              Load the latest mapping
            </button>
          )}
          {attempt.items.flatMap((it) =>
            it.slots.map((s) => (
              <fieldset key={s.key} className="space-y-2 rounded-xl border border-border bg-surface p-3">
                <legend className="px-1 font-medium">
                  {s.label} · {marks(s.max_units)} marks
                </legend>
                <div className="flex flex-wrap gap-3 text-sm">
                  {pages.length === 0 && <span className="text-muted">Upload your pages first.</span>}
                  {pages.map((p) => (
                    <label key={p.id} className="flex items-center gap-2">
                      <input type="checkbox" checked={slots[s.key]?.pages.includes(p.id) ?? false} onChange={(e) => togglePage(s.key, p.id, e.target.checked)} />
                      {pageLabel(p.id)}
                    </label>
                  ))}
                  <label className="flex items-center gap-2 text-muted">
                    <input type="checkbox" checked={slots[s.key]?.unanswered ?? false} onChange={(e) => toggleUnanswered(s.key, e.target.checked)} />I didn&apos;t answer this
                  </label>
                </div>
              </fieldset>
            )),
          )}
          {sealError && (
            <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
              {sealError}
            </p>
          )}
          <button
            type="button"
            onClick={() => void submit()}
            disabled={sealing || !complete || uploads.some((u) => u.status === "uploading")}
            className="rounded-lg bg-accent px-5 py-3 font-medium text-white hover:bg-accent-strong disabled:opacity-60 dark:text-background"
          >
            {sealing ? "Submitting…" : "Submit for marking"}
          </button>
          {!complete && <p className="text-sm text-muted">Give every part at least one page, or tick “I didn&apos;t answer this”.</p>}
        </section>
      )}
    </div>
  );
}
