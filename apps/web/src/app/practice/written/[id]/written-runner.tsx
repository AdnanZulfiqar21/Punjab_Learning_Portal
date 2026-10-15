"use client";

// Written-script runner (W03/W04). States are kept distinct and honest: a file chosen on this device, uploading,
// uploaded but NOT submitted, and submitted (sealed with a receipt). Nothing is marked until it is submitted.
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { EvidenceLink, NextSteps as Steps, WrittenAttempt, WrittenPage, WrittenResult } from "@portal/contracts";
import { saveMapping, sealScript, transformPage } from "@/app/actions/written";
import { LessonBlocks } from "@/components/lesson-blocks";
import { PendingAction } from "./pending-action";
import { PractiseAgain } from "./practise-again";
import { RecheckPanel } from "./recheck-panel";
import { Notice } from "@/components/ui";
import { HelpLink } from "@/components/help-link";
import { TIME_ZONE } from "@/lib/dates";
import { reach } from "@/lib/reach";

type Slot = { pages: string[]; unanswered: boolean };
type Upload = { id: string; name: string; progress: number; status: "uploading" | "failed"; error?: string; retryable?: boolean };
const marks = (u: number) => String(u / 100);
// WRITTEN-CONNECTION-01 (W04.S2.T1): a request that never reached the server is a failure like any other.
const UNREACHABLE = "Can't reach the service. Check your connection; nothing on this page is lost.";
function onConnectionChange(notify: () => void) {
  window.addEventListener("online", notify);
  window.addEventListener("offline", notify);
  return () => {
    window.removeEventListener("online", notify);
    window.removeEventListener("offline", notify);
  };
}
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { timeStyle: "short", dateStyle: "medium", timeZone: TIME_ZONE });

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

export function WrittenRunner({
  attempt,
  result = null,
  canStraighten = false,
}: {
  attempt: WrittenAttempt;
  result?: WrittenResult | null;
  canStraighten?: boolean;
}) {
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
  const syncedWith = useRef<string | null>(null); // the server time the offset was last measured against
  const reconnect = useRef<() => void>(() => undefined);
  const online = useSyncExternalStore(onConnectionChange, () => navigator.onLine, () => true);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savingPromise = useRef<Promise<boolean> | null>(null);
  // W03.S3.T3 (UPLOAD-RETRY-01): a failed upload keeps its file on this device so it can be sent again. The server
  // recognises the same file, so a retry after a lost acknowledgement never adds a second page.
  const pendingFiles = useRef(new Map<string, File>());
  const revisionRef = useRef(attempt.manifest_revision);
  const active = attempt.status === "active";
  const cutoff = new Date(attempt.upload_cutoff_at).getTime();
  const closed = now !== null && now > cutoff;

  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => {
      // W04.S2.T1: measured again whenever a fresh server time arrives (after a reconnect or a return to this tab), so
      // a device clock that was changed or drifted while asleep doesn't misstate the time left.
      if (offset.current === null || syncedWith.current !== attempt.server_now) {
        offset.current = new Date(attempt.server_now).getTime() - Date.now();
        syncedWith.current = attempt.server_now;
      }
      setNow(Date.now() + offset.current);
    }, 1000);
    return () => clearInterval(t);
  }, [active, attempt.server_now]);

  // Back online, or back on this tab: fetch the attempt again (a fresh server time, and its real status) and send a page
  // map that couldn't be saved. The handler is refreshed every render so it sees the current map.
  useEffect(() => {
    reconnect.current = () => {
      if (mapState === "error") persistMapping(slots);
      router.refresh();
    };
  });
  useEffect(() => {
    if (!active) return;
    const back = () => reconnect.current();
    const visible = () => {
      if (document.visibilityState === "visible") reconnect.current();
    };
    window.addEventListener("online", back);
    document.addEventListener("visibilitychange", visible);
    return () => {
      window.removeEventListener("online", back);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [active]);

  useEffect(() => {
    if (closed) router.refresh(); // the server expires the attempt after U; show its honest state
  }, [closed, router]);

  async function sendFile(file: File, tmp: string, retry: boolean) {
    pendingFiles.current.set(tmp, file);
    setUploads((u) => (retry ? u.map((x) => (x.id === tmp ? { ...x, progress: 0, status: "uploading", error: undefined } : x)) : [...u, { id: tmp, name: file.name, progress: 0, status: "uploading" }]));
    const res = await uploadFile(attempt.id, file, (p) => setUploads((u) => u.map((x) => (x.id === tmp ? { ...x, progress: p } : x))));
    if (res.status === 201) {
      const body = res.body as { pages: WrittenPage[]; duplicate: boolean; warnings: string[] };
      pendingFiles.current.delete(tmp);
      setUploads((u) => u.filter((x) => x.id !== tmp));
      setPages((p) => [...p, ...body.pages.filter((n) => !p.some((x) => x.id === n.id))]); // a PDF adds one page per PDF page
      // SCAN-QUALITY-01: quality warnings are shown with each page below. A retry that reached the server the first
      // time returns the same pages; only a deliberate second copy needs a note here.
      if (body.duplicate && !retry) setNotes((n) => [...n, `${file.name} was already uploaded.`]);
    } else {
      const detail = (res.body as { detail?: string } | null)?.detail;
      const lost = res.status === 0;
      setUploads((u) =>
        u.map((x) =>
          x.id === tmp
            ? { ...x, status: "failed", retryable: lost || res.status >= 500, error: detail ?? (lost ? "Connection lost. Your file is kept on this device: try again." : `Upload failed (${res.status}).`) }
            : x,
        ),
      );
    }
  }

  async function addFiles(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) await sendFile(file, crypto.randomUUID(), false);
  }

  function retryUpload(tmp: string) {
    const file = pendingFiles.current.get(tmp);
    if (file) void sendFile(file, tmp, true);
  }

  function dismissUpload(tmp: string) {
    pendingFiles.current.delete(tmp);
    setUploads((u) => u.filter((x) => x.id !== tmp));
  }

  function persistMapping(next: Record<string, Slot>) {
    setSlots(next);
    setMapState("saving");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveTimer.current = null;
      savingPromise.current = (async () => {
        const out = await reach(() => saveMapping(attempt.id, revisionRef.current, next), { kind: "error", message: UNREACHABLE } as const);
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
    // The map must be saved before sealing: send it now if a save is waiting, or if the last one failed (for example
    // while offline); never refuse just because an earlier attempt to save it failed.
    let saved = mapState === "saved";
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
      saveTimer.current = null;
      saved = false;
    } else if (savingPromise.current) {
      saved = await savingPromise.current;
    }
    if (!saved) {
      const out = await reach(() => saveMapping(attempt.id, revisionRef.current, slots), { kind: "error", message: UNREACHABLE } as const);
      if (out.kind !== "ok") {
        setMapState(out.kind === "conflict" ? "conflict" : "error"); // shown truthfully, and sent again on reconnect
        setMapError(out.message);
        setSealing(false);
        setSealError(out.message);
        return;
      }
      revisionRef.current = out.attempt.manifest_revision;
      setRevision(out.attempt.manifest_revision);
      setMapState("saved");
      setMapError(null);
    }
    const storageKey = `written-seal:${attempt.id}`;
    let key: string;
    try {
      key = window.localStorage.getItem(storageKey) ?? crypto.randomUUID().replaceAll("-", "");
      window.localStorage.setItem(storageKey, key);
    } catch {
      key = crypto.randomUUID().replaceAll("-", "");
    }
    const out = await reach(() => sealScript(attempt.id, key, revisionRef.current), { kind: "error", message: UNREACHABLE } as const);
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
        {attempt.status === "expired" && attempt.end_reason === "plan_withdrawn" && (
          // PERMITS-01: a refund or revocation ended this unsealed test; pages are kept, nothing was marked.
          <Notice tone="warn" title="This test ended because your plan was withdrawn">
            {pages.length} page(s) you uploaded are kept but weren&apos;t submitted, so they won&apos;t be marked. Tests you had already submitted are
            still marked.
          </Notice>
        )}
        {attempt.status === "expired" && attempt.end_reason !== "plan_withdrawn" && (
          <Notice tone="warn" title="The upload window closed before you submitted">
            {pages.length} page(s) reached the server but were not submitted, so they won&apos;t be marked. You can start a new practice test.{" "}
            <HelpLink slug="written-submission-receipt">How submitting and time limits work</HelpLink>
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
        {active && !online && (
          // W04.S2.T1 (WRITTEN-CONNECTION-01): what an outage means for a written test, which keeps no pages offline.
          <Notice tone="warn" title="You're offline">
            Time keeps running: upload and submit by {when(attempt.upload_cutoff_at)}. Pages can&apos;t upload until you&apos;re back online; a page that
            fails stays in this tab so you can send it again. Your page choices are sent as soon as you&apos;re back.
          </Notice>
        )}
      </header>

      {attempt.status === "sealed" && (
        <section aria-labelledby="result-h" className="space-y-3">
          <h2 id="result-h" className="text-lg font-semibold">
            Your marks
          </h2>
          {result && (result.status === "released" || result.work_status === "delayed") && <WorkStatus status={result.work_status} />}
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
                      : result.decision_method === "SYSTEM" && result.versions.at(-1)?.case_kind === "regrade"
                        ? "marked by a teacher; carried forward unchanged after a marking-guide correction"
                        : "marked by a teacher"}
                  </span>
                </p>
              ) : result.assessment_state === "unavailable" ? (
                // COMPLETENESS-01 (§20.9.3): nothing could be assessed, so there is no mark at all, not a zero.
                <Notice tone="warn" title="No mark for this test">
                  None of the questions could be assessed, so this test has no mark. The allowance it used was returned; the reasons are shown with each
                  question below.
                </Notice>
              ) : (
                <PartialMarks result={result} />
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
                    <p className="text-sm text-muted" dir="auto">
                      {q.status_reason}
                      {q.status === "unavailable" && " The allowance for this question was returned to your plan."}
                    </p>
                  )}
                  {q.academic_review === "open" && (
                    // ACADEMIC-REVIEW-01: the guide doesn't cover the method yet; no score is forced meanwhile.
                    <p className="text-sm text-muted">
                      A senior subject reviewer is checking how the marking guide applies to your answer. This question has no mark until then, and
                      nothing is counted as zero.
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
                        {/* W07.S3.T1: a teacher may write in Urdu; the browser sets each comment's direction from its text. */}
                        {c.reason && (
                          <span className="block text-muted" dir="auto">
                            {c.reason}
                          </span>
                        )}
                        {(c.evidence ?? []).map((e, k) => (
                          <EvidencePlace key={k} attemptId={attempt.id} place={e} />
                        ))}
                      </li>
                    ))}
                  </ul>
                  {q.next_steps && <NextSteps steps={q.next_steps} />}
                  {/* MODEL-ANSWER-01 (W07.S1.T3): released with the mark, from the marking guide that marked it. */}
                  {q.model_answer && q.model_answer.length > 0 && (
                    <details className="rounded-lg border border-border p-3 text-sm">
                      <summary className="cursor-pointer font-medium text-accent">Worked answer for question {q.position}</summary>
                      <div className="mt-2 space-y-2">
                        {q.model_answer_note && <p className="text-muted">{q.model_answer_note}</p>}
                        <LessonBlocks blocks={q.model_answer as { type: string }[]} headingOffset={4} />
                      </div>
                    </details>
                  )}
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
              <img
                src={`/practice/written/${attempt.id}/pages/${p.id}?v=${encodeURIComponent(JSON.stringify(p.transform ?? {}))}`}
                alt={`Page ${i + 1}`}
                loading="lazy" // W07.S3.T1: large scans load as they scroll into view; the fixed height keeps the layout still
                decoding="async"
                className="h-40 w-full rounded object-contain"
              />
              <p>
                Page {i + 1} · {attempt.status === "sealed" ? "submitted" : "uploaded, not yet submitted"}
              </p>
              {p.file_pages > 1 && (
                <p className="text-muted">
                  PDF page {p.page_index} of {p.file_pages}
                </p>
              )}
              {active && (
                <PageAdjust
                  attemptId={attempt.id}
                  page={p}
                  number={i + 1}
                  canStraighten={canStraighten}
                  onChange={(n) => setPages((all) => all.map((x) => (x.id === n.id ? n : x)))}
                />
              )}
              {(p.quality ?? []).length > 0 && (
                <ul className="space-y-1 text-warn" aria-label={`Photo checks for page ${i + 1}`}>
                  {(p.quality ?? []).map((q) => (
                    <li key={q.code}>
                      {q.message}
                      {/* NEAR-DUP-01: which page it looks like, by its number in this list. */}
                      {q.like_page_id && pages.some((x) => x.id === q.like_page_id) && ` (It looks like page ${pages.findIndex((x) => x.id === q.like_page_id) + 1}.)`}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
          {uploads.map((u) => (
            <li key={u.id} className="rounded-lg border border-dashed border-border p-2 text-sm" role="status">
              <p className="truncate">{u.name}</p>
              {u.status === "uploading" ? (
                <progress max={100} value={u.progress} className="w-full" aria-label={`Uploading ${u.name}`} />
              ) : (
                <>
                  <p className="text-danger">
                    {u.error} <HelpLink slug="written-upload-limits">What can I upload?</HelpLink>
                  </p>
                  <p className="mt-1 flex gap-3">
                    {u.retryable && active && (
                      <button type="button" onClick={() => retryUpload(u.id)} className="text-accent underline underline-offset-2">
                        Try {u.name} again
                      </button>
                    )}
                    <button type="button" onClick={() => dismissUpload(u.id)} className="text-muted underline underline-offset-2">
                      Remove from this list
                    </button>
                  </p>
                </>
              )}
            </li>
          ))}
        </ul>
        {active && pages.some((p) => (p.quality ?? []).length > 0) && (
          <p className="text-sm text-muted">
            These are automatic checks, not a judgement: a teacher decides whether a page can be read. To use a clearer photo, add it and choose
            it for that answer below. A page you don&apos;t choose for any answer isn&apos;t sent for marking.
          </p>
        )}
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

// W07.S1.T2 (FEEDBACK-EVIDENCE-01): the place on your page a comment is about. The region is a fraction of the upright
// page preview, so it is drawn over the same image at any size. A scan that is no longer available is named, never
// highlighted.
// RESULT-ARITHMETIC-01 (§20.9.3, W07.S1.T1): an incomplete paper shows the marks awarded on the scored questions, the
// marks still being marked and the marks that couldn't be assessed side by side, which add up to the whole test. There
// is no total or percentage for the paper, and the teacher label covers only the scored questions.
function PartialMarks({ result }: { result: WrittenResult }) {
  const scored = result.scored_max_units ?? 0;
  const pending = result.pending_max_units ?? 0;
  const unavailable = result.unavailable_max_units ?? 0;
  const stillMarking = result.completeness === "partial_pending";
  return (
    <Notice tone="warn" title={stillMarking ? "Marking isn't finished yet" : "Some questions couldn't be assessed"}>
      <p>
        {scored > 0
          ? `${marks(result.total_units ?? 0)} out of ${marks(scored)} on the questions a teacher marked.`
          : "No question has been marked yet."}
      </p>
      <dl aria-label="How the marks add up" className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 tabular-nums">
        <dt>Marked</dt>
        <dd>{marks(scored)} marks</dd>
        {pending > 0 && (
          <>
            <dt>Still being marked</dt>
            <dd>{marks(pending)} marks</dd>
          </>
        )}
        {unavailable > 0 && (
          <>
            <dt>Couldn&apos;t be assessed</dt>
            <dd>{marks(unavailable)} marks</dd>
          </>
        )}
        <dt className="font-medium">Whole test</dt>
        <dd className="font-medium">{marks(result.max_units)} marks</dd>
      </dl>
      <p className="mt-2">
        {stillMarking
          ? "There is no final total until every question is resolved, and nothing is counted as zero just because it wasn't assessed."
          : "This test has no final total or percentage, because some questions couldn't be assessed. They aren't counted as zero."}
      </p>
    </Notice>
  );
}

// §20.9.3: what is happening to the script now, kept apart from the marks.
function WorkStatus({ status }: { status: WrittenResult["work_status"] }) {
  if (status === "action_required") return <p className="text-sm font-medium">Your step: a teacher asked you for something on a question below.</p>;
  if (status === "delayed")
    return (
      <p className="text-sm font-medium">Marking is taking longer than planned. Your script is still in the queue, and nothing has been lost.</p>
    );
  if (status === "in_review") return <p className="text-sm text-muted">A teacher is still working on this script.</p>;
  return null;
}

function EvidencePlace({ attemptId, place }: { attemptId: string; place: EvidenceLink }) {
  if (!place.available) return <span className="block text-sm text-muted">About {place.where}: that scan is no longer available.</span>;
  const r = place.region;
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-accent">Show where: {place.where}</summary>
      <span className="relative mt-1 inline-block w-full max-w-sm">
        {/* eslint-disable-next-line @next/next/no-img-element -- private, uncached preview served by our own route */}
        <img
          src={`/practice/written/${attemptId}/pages/${place.page_id}`}
          alt={place.clearer_copy ? `Your clearer copy, page ${place.page_number}` : `Your page ${place.page_number}`}
          loading="lazy"
          decoding="async"
          className="block w-full rounded border border-border"
        />
        {r && (
          <span
            aria-hidden="true"
            className="absolute rounded border-4 border-warn"
            style={{ left: `${r[0] * 100}%`, top: `${r[1] * 100}%`, width: `${r[2] * 100}%`, height: `${r[3] * 100}%` }}
          />
        )}
      </span>
    </details>
  );
}

// W07.S2.T1 (NEXT-STEPS-01): what to work on next, in the rubric's own approved words, and the reviewed lessons for
// this question's topic. When none is published yet it says so and points to the chapter page; nothing is generated.
function NextSteps({ steps }: { steps: Steps }) {
  return (
    <section aria-label="Next steps" className="space-y-2 rounded-lg border border-border bg-surface-muted p-3 text-sm">
      <p className="font-medium">Next steps</p>
      {steps.focus.length > 0 && (
        <ul className="list-disc space-y-1 pl-5">
          {steps.focus.map((f) => (
            <li key={f.criterion_id}>
              Work on: {f.description}
              {f.common_mistakes.length > 0 && <span className="block text-muted">Common mistakes: {f.common_mistakes.join("; ")}</span>}
            </li>
          ))}
        </ul>
      )}
      {steps.lessons.length > 0 ? (
        <p>
          Revise:{" "}
          {steps.lessons.map((l, i) => (
            <span key={l.id}>
              {i > 0 && ", "}
              <a href={`/learn/chapter/${l.chapter_id}#lesson-${l.id}`} className="text-accent underline underline-offset-2">
                {l.title}
              </a>
            </span>
          ))}
        </p>
      ) : (
        <p className="text-muted">
          No reviewed lesson is published for this topic yet.
          {steps.chapter_id && (
            <>
              {" "}
              <a href={`/learn/chapter/${steps.chapter_id}`} className="text-accent underline underline-offset-2">
                Open the chapter
              </a>{" "}
              for its outline and textbook pages.
            </>
          )}
        </p>
      )}
    </section>
  );
}

// W03.S1.T3 (TRANSFORMS-01): turn a page, make its contrast clearer or trim its edges before submitting. Each is
// applied to a fresh copy of the original, which is always kept; teachers can see the original too. STRAIGHTEN-01: where
// rolled out, a crooked photo can be straightened (the angle is found from the writing); undo is always offered.
function PageAdjust({
  attemptId,
  page,
  number,
  canStraighten,
  onChange,
}: {
  attemptId: string;
  page: WrittenPage;
  number: number;
  canStraighten: boolean;
  onChange: (p: WrittenPage) => void;
}) {
  const t = page.transform ?? { rotate: 0, crop: null, enhance: false, straighten: 0, aspect: null, shown_crop: null };
  const angle = t.straighten ?? 0;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trim, setTrim] = useState({ top: 0, bottom: 0, left: 0, right: 0 });
  const apply = async (body: Parameters<typeof transformPage>[2]) => {
    setBusy(true);
    setError(null);
    const r = await reach(() => transformPage(attemptId, page.id, body), { ok: false, error: UNREACHABLE } as const);
    setBusy(false);
    if (r.ok) onChange(r.page);
    else setError(r.error);
  };
  const keep = { rotate: t.rotate, crop: t.crop ?? null, enhance: t.enhance, straighten: angle, shown_crop: t.shown_crop ?? null };
  const small = "rounded border border-border bg-surface px-2 py-1 hover:border-accent disabled:opacity-60";
  return (
    <div role="group" aria-label={`Adjust page ${number}`} className="space-y-1">
      <div className="flex flex-wrap items-center gap-1">
        <button type="button" disabled={busy} className={small} onClick={() => apply({ ...keep, rotate: ((t.rotate + 270) % 360) as 0 | 90 | 180 | 270 })}>
          Turn left
        </button>
        <button type="button" disabled={busy} className={small} onClick={() => apply({ ...keep, rotate: ((t.rotate + 90) % 360) as 0 | 90 | 180 | 270 })}>
          Turn right
        </button>
        <label className="flex items-center gap-1">
          <input type="checkbox" disabled={busy} checked={t.enhance} onChange={(e) => apply({ ...keep, enhance: e.target.checked })} />
          Clearer contrast
        </label>
        {canStraighten && !angle && (
          <button type="button" disabled={busy} className={small} onClick={() => apply({ ...keep, straighten: "auto", shown_crop: null })}>
            Straighten
          </button>
        )}
        {angle !== 0 && (
          <>
            <span className="text-muted">Straightened by {Math.abs(angle).toFixed(1)}°</span>
            <button type="button" disabled={busy} className={small} onClick={() => apply({ ...keep, straighten: 0, shown_crop: null })}>
              Undo straighten
            </button>
          </>
        )}
      </div>
      <details>
        <summary className="cursor-pointer">Trim edges</summary>
        <div className="mt-1 grid grid-cols-2 gap-1">
          {(["top", "bottom", "left", "right"] as const).map((side) => (
            <label key={side} className="flex items-center gap-1">
              <span className="w-14 capitalize">{side}</span>
              <input
                type="number"
                min={0}
                max={30}
                step={1}
                value={trim[side]}
                onChange={(e) => setTrim((v) => ({ ...v, [side]: Math.max(0, Math.min(30, Number(e.target.value) || 0)) }))}
                aria-label={`Trim from the ${side} (% of the page as shown)`}
                className="w-16 rounded border border-border bg-surface px-1 py-0.5"
              />
              %
            </label>
          ))}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          <button
            type="button"
            disabled={busy || trim.top + trim.bottom + trim.left + trim.right === 0}
            className={small}
            onClick={() =>
              apply({
                ...keep,
                trim: [trim.left / 100, trim.top / 100, 1 - (trim.left + trim.right) / 100, 1 - (trim.top + trim.bottom) / 100],
              })
            }
          >
            Trim
          </button>
          {(t.crop || t.shown_crop) && (
            <button type="button" disabled={busy} className={small} onClick={() => apply({ ...keep, crop: null, shown_crop: null })}>
              Undo trim
            </button>
          )}
        </div>
      </details>
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
