"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, useTransition } from "react";
import type { StudioHistoryEvent, StudioItem } from "@portal/contracts";
import {
  claimItem,
  publishItem,
  quarantineItem,
  recordScoreCorrection,
  rollbackItem,
  setQuestionPool,
  setAccessTier,
  releaseItem,
  retireItem,
  reviewItem,
  reviseItem,
  saveDraft,
  submitItem,
  withdrawItem,
  type ActionResult,
  type Block,
  type ConflictState,
  type SourceRef,
} from "@/app/actions/studio";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Badge, Notice } from "@/components/ui";
import { GRADE_LABEL } from "@/lib/format";
import { BlockEditor, normaliseBlocks, SourceRefsEditor } from "./block-editor";
import { McqEditor, McqPreview, mcqSections, normaliseMcq } from "./mcq-editor";
import { normaliseStoryboard, StoryboardEditor, StoryboardPreview } from "./storyboard-editor";
import {
  normaliseRubric,
  normaliseWritten,
  RubricEditor,
  RubricPreview,
  WrittenEditor,
  WrittenPreview,
  writtenSections,
  type QuestionVersionChoice,
} from "./written-editor";

const STATE_LABEL: Record<string, string> = {
  draft: "Draft",
  submitted: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  published: "Published",
};
const AVAILABILITY_LABEL: Record<string, string> = {
  unpublished: "Not published",
  live: "Live for learners",
  quarantined: "Quarantined",
  retired: "Retired",
};
const AUTOSAVE_MS = 1500;
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

type Body = Record<string, unknown>;
type Draft = { title: string; body: Body; refs: SourceRef[] };

const blocksOf = (body: Body) => (Array.isArray(body.blocks) ? (body.blocks as Block[]) : []);

function normaliseBody(kind: string, body: Body): Body {
  if (kind === "mcq") return normaliseMcq(body);
  if (kind === "written") return normaliseWritten(body);
  if (kind === "rubric") return normaliseRubric(body);
  if (kind === "storyboard") return normaliseStoryboard(body);
  return { blocks: normaliseBlocks(blocksOf(body)) };
}

function Preview({ kind, body }: { kind: string; body: Body }) {
  if (kind === "mcq") return <McqPreview body={body} />;
  if (kind === "written") return <WrittenPreview body={body} />;
  if (kind === "rubric") return <RubricPreview body={body} />;
  if (kind === "storyboard") return <StoryboardPreview body={body} />;
  return <LessonBlocks blocks={blocksOf(body)} headingOffset={1} />;
}

function sections(kind: string, body: Body): { label: string; text: string }[] {
  if (kind === "mcq") return mcqSections(body);
  if (kind === "written" || kind === "rubric") return writtenSections(kind, body);
  if (kind === "storyboard") return Object.entries(body).map(([k, v]) => ({ label: k, text: JSON.stringify(v) }));
  return blocksOf(body).map((b, i) => ({ label: `Block ${i + 1}`, text: JSON.stringify(b) }));
}

function summarise(kind: string, label: string, text: string | undefined): string {
  if (text === undefined) return "(none)";
  if (kind !== "mcq" || label === "Correct answer") {
    try {
      const b = JSON.parse(text) as Block;
      if (b && typeof b === "object" && "type" in b) {
        return `${b.type}: ${String(b.text ?? b.caption ?? b.latex ?? (Array.isArray(b.items) ? b.items.join(", ") : "")).slice(0, 160)}`;
      }
    } catch {
      /* plain value */
    }
    return text.slice(0, 160);
  }
  return text.replace(/[{}"[\]]/g, " ").replace(/\s+/g, " ").slice(0, 160);
}
type SaveStatus = { kind: "saved" | "dirty" | "saving" | "error"; message?: string; errors?: string[] };

// ------------------------------------------------------------------ local recovery (P06.S1.T3)
const storageKey = (id: string) => `studio-draft:${id}`;
function readLocal(id: string): string | null {
  try {
    return window.localStorage.getItem(storageKey(id));
  } catch {
    return null;
  }
}
function writeLocal(id: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(storageKey(id));
    else window.localStorage.setItem(storageKey(id), value);
  } catch {
    /* storage unavailable: autosave to the server still protects the work */
  }
}
const noopSubscribe = () => () => {};

export function Workspace({
  item,
  history,
  myId,
  questionVersions = [],
}: {
  item: StudioItem;
  history: StudioHistoryEvent[];
  myId: string;
  questionVersions?: QuestionVersionChoice[];
}) {
  const router = useRouter();
  const working = item.working;
  const editable = item.actions.edit && !!working;
  const initial: Draft = {
    title: item.title,
    body: (working?.body as Body | undefined) ?? {},
    refs: (working?.source_refs as SourceRef[] | undefined) ?? [],
  };
  const [draft, setDraft] = useState<Draft>(initial);
  const [revision, setRevision] = useState(working?.revision ?? 1);
  const [status, setStatus] = useState<SaveStatus>({ kind: "saved" });
  const [conflict, setConflict] = useState<ConflictState | null>(null);
  const [tab, setTab] = useState<"edit" | "preview">(editable ? "edit" : "preview");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saving = useRef<Promise<boolean> | null>(null);

  // Unsaved work from an earlier visit (same base revision) can be restored.
  const stored = useSyncExternalStore(noopSubscribe, () => readLocal(item.id), () => null);
  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const recovery = (() => {
    if (!editable || recoveryDismissed || !stored) return null;
    try {
      const parsed = JSON.parse(stored) as Draft & { baseRevision: number; at: string };
      const same = JSON.stringify([parsed.title, parsed.body, parsed.refs]) === JSON.stringify([initial.title, initial.body, initial.refs]);
      return parsed.baseRevision === working?.revision && !same ? parsed : null;
    } catch {
      return null;
    }
  })();

  // The latest revision the server acknowledged; saves are chained so a new save never starts from a stale one.
  const revisionRef = useRef(revision);
  const save = useCallback(
    async (next: Draft, rev: number): Promise<boolean> => {
      setStatus({ kind: "saving" });
      const res = await saveDraft(item.id, rev, next.title, normaliseBody(item.kind, next.body), next.refs);
      if (res.ok) {
        revisionRef.current = res.item.working?.revision ?? rev + 1;
        setRevision(revisionRef.current);
        setStatus({ kind: "saved" });
        writeLocal(item.id, null);
        return true;
      }
      if (res.conflict) {
        setConflict(res.conflict);
        setStatus({ kind: "error", message: "Not saved: someone else changed this draft." });
      } else {
        setStatus({ kind: "error", message: res.error, errors: res.errors });
      }
      return false;
    },
    [item.id, item.kind],
  );

  function change(next: Draft) {
    setDraft(next);
    setStatus({ kind: "dirty" });
    writeLocal(item.id, JSON.stringify({ ...next, baseRevision: revisionRef.current, at: new Date().toISOString() }));
    if (conflict) return; // never autosave over someone else's newer work
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      timer.current = null;
      saving.current = chain(next);
    }, AUTOSAVE_MS);
  }

  function chain(next: Draft): Promise<boolean> {
    const previous = saving.current;
    return (async () => {
      if (previous && !(await previous)) return false; // a failed or conflicting save stops the chain
      return save(next, revisionRef.current);
    })();
  }

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  // Warn before leaving with unsaved edits.
  useEffect(() => {
    if (status.kind !== "dirty" && status.kind !== "saving") return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [status.kind]);

  /** Flush pending edits before a workflow action. */
  async function flush(): Promise<boolean> {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
      saving.current = chain(draft);
    }
    if (saving.current) return saving.current;
    return status.kind !== "error" && !conflict;
  }

  function resolveConflict(keep: "theirs" | "mine") {
    if (!conflict) return;
    if (keep === "theirs") {
      writeLocal(item.id, null);
      setConflict(null);
      router.refresh();
      return;
    }
    revisionRef.current = conflict.revision;
    setConflict(null);
    setRevision(conflict.revision);
    saving.current = save(draft, conflict.revision);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0 space-y-4" aria-label="Content">
        <Header item={item} />
        {recovery && (
          <Notice tone="warn" title="Unsaved changes from an earlier session">
            <span className="block">Saved in this browser at {when(recovery.at)} but never reached the server.</span>
            <span className="mt-2 flex gap-2">
              <button type="button" className="underline" onClick={() => { setRecoveryDismissed(true); change({ title: recovery.title, body: recovery.body, refs: recovery.refs }); }}>
                Restore them
              </button>
              <button type="button" className="underline" onClick={() => { writeLocal(item.id, null); setRecoveryDismissed(true); }}>
                Discard
              </button>
            </span>
          </Notice>
        )}
        {conflict && <ConflictPanel kind={item.kind} conflict={conflict} mine={draft} onResolve={resolveConflict} />}
        <div role="tablist" aria-label="View" className="flex gap-2">
          {(["edit", "preview"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              type="button"
              onClick={() => setTab(t)}
              disabled={t === "edit" && !editable}
              className={`rounded-lg px-3 py-1.5 text-sm ${tab === t ? "bg-accent-soft font-medium text-accent" : "text-muted hover:text-foreground"} disabled:opacity-40`}
            >
              {t === "edit" ? "Edit" : "Preview"}
            </button>
          ))}
          {editable && <SaveIndicator status={status} revision={revision} />}
        </div>
        {status.kind === "error" && status.errors && status.errors.length > 0 && (
          <ul role="alert" className="list-disc space-y-1 rounded-lg border border-danger/30 bg-danger-soft py-2 pr-3 pl-8 text-sm">
            {status.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        )}
        {tab === "edit" && editable ? (
          <div className="space-y-6">
            <div className="space-y-1">
              <label htmlFor="title" className="font-medium">
                Title
              </label>
              <input id="title" value={draft.title} onChange={(e) => change({ ...draft, title: e.target.value })} className="w-full rounded-lg border border-border bg-surface px-3 py-2" maxLength={200} />
            </div>
            {item.kind === "mcq" ? (
              <McqEditor body={draft.body} onChange={(body) => change({ ...draft, body })} />
            ) : item.kind === "written" ? (
              <WrittenEditor body={draft.body} onChange={(body) => change({ ...draft, body })} />
            ) : item.kind === "storyboard" ? (
              <StoryboardEditor body={draft.body} onChange={(body) => change({ ...draft, body })} refCount={draft.refs.length} />
            ) : item.kind === "rubric" ? (
              <RubricEditor body={draft.body} onChange={(body) => change({ ...draft, body })} versions={questionVersions} />
            ) : (
              <BlockEditor blocks={blocksOf(draft.body)} onChange={(blocks) => change({ ...draft, body: { blocks } })} />
            )}
            <SourceRefsEditor
              refs={draft.refs}
              onChange={(refs) => change({ ...draft, refs })}
              sourceId={item.source.id}
              sourceLabel={`${item.source.source_id}${item.source.title ? ` (${item.source.title})` : ""}`}
              pdfPages={item.source.pdf_pages}
              chapterRange={[item.chapter_pdf_start ?? null, item.chapter_pdf_end ?? null]}
            />
          </div>
        ) : (
          <article className="space-y-4 rounded-xl border border-border bg-surface p-5">
            <h2 className="text-2xl font-semibold tracking-tight">{draft.title}</h2>
            <Preview kind={item.kind} body={draft.body} />
            <SourceList refs={draft.refs} label={item.source.source_id} />
          </article>
        )}
        {item.published && (
          <details className="rounded-xl border border-border bg-surface p-4">
            <summary className="cursor-pointer font-medium">Learners currently see version {item.published.number}</summary>
            <div className="mt-4">
              <Preview kind={item.kind} body={item.published.body as Body} />
            </div>
          </details>
        )}
      </section>
      <aside className="space-y-4" aria-label="Workflow">
        <ActionsPanel item={item} myId={myId} flush={flush} />
        <Feedback item={item} />
        <History events={history} />
      </aside>
    </div>
  );
}

function Header({ item }: { item: StudioItem }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted">
        {GRADE_LABEL[item.grade_number]} · {item.subject_code.replace("_", " ")} · {item.chapter_title}
        {item.topic_title ? ` · ${item.topic_title}` : ""}
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">{item.title}</h1>
      <div className="flex flex-wrap gap-2">
        <Badge tone={item.state === "changes_requested" ? "warn" : item.state === "approved" || item.state === "published" ? "ok" : "info"}>
          {STATE_LABEL[item.state]}
          {item.working_version ? ` · version ${item.working_version}` : ""}
        </Badge>
        <Badge tone={item.availability === "live" ? "ok" : item.availability === "unpublished" ? "info" : "warn"}>
          {AVAILABILITY_LABEL[item.availability]}
        </Badge>
        <Badge tone={item.source.publication_rights === "CONFIRMED" ? "ok" : "warn"}>
          Rights {item.source.publication_rights.toLowerCase()}
        </Badge>
      </div>
      {item.availability_reason && <p className="text-sm text-muted">Reason: {item.availability_reason}</p>}
    </div>
  );
}

function SaveIndicator({ status, revision }: { status: SaveStatus; revision: number }) {
  const text =
    status.kind === "saving"
      ? "Saving…"
      : status.kind === "dirty"
        ? "Unsaved changes"
        : status.kind === "error"
          ? (status.message ?? "Not saved")
          : `Saved · revision ${revision}`;
  return (
    <span role="status" aria-live="polite" className={`ml-auto self-center text-sm ${status.kind === "error" ? "text-danger" : "text-muted"}`}>
      {text}
    </span>
  );
}

function SourceList({ refs, label }: { refs: SourceRef[]; label: string }) {
  if (refs.length === 0) return <p className="text-sm text-warn">No source pages referenced yet.</p>;
  return (
    <p className="border-t border-border pt-3 text-sm text-muted">
      Source: {label}, PDF {refs.map((r) => (r.pdf_from === r.pdf_to ? `p. ${r.pdf_from}` : `pp. ${r.pdf_from}–${r.pdf_to}`)).join("; ")}
    </p>
  );
}

function ConflictPanel({
  kind,
  conflict,
  mine,
  onResolve,
}: {
  kind: string;
  conflict: ConflictState;
  mine: Draft;
  onResolve: (k: "theirs" | "mine") => void;
}) {
  const theirs = new Map(sections(kind, conflict.body as Body).map((x) => [x.label, x.text]));
  const yours = new Map(sections(kind, mine.body).map((x) => [x.label, x.text]));
  const labels = [...new Set([...theirs.keys(), ...yours.keys()])];
  const rows = labels.filter((l) => theirs.get(l) !== yours.get(l)).map((l) => ({ l, a: theirs.get(l), b: yours.get(l) }));
  return (
    <section role="alert" className="space-y-3 rounded-xl border border-warn bg-warn-soft p-4">
      <h2 className="font-semibold">Someone else saved a newer version</h2>
      <p className="text-sm">
        {conflict.updated_by ?? "Another editor"} saved revision {conflict.revision} at {when(conflict.updated_at)}. Nothing was overwritten. Compare
        the differences, then choose which text to keep.
      </p>
      {conflict.title !== mine.title && (
        <p className="text-sm">
          Title: theirs “{conflict.title}” · yours “{mine.title}”
        </p>
      )}
      <ul className="space-y-2 text-sm">
        {rows.length === 0 && <li>The content is identical; only source references or the title differ.</li>}
        {rows.map((r) => (
          <li key={r.l} className="grid gap-1 rounded-lg bg-surface p-2 sm:grid-cols-2">
            <span>
              <span className="font-medium">{r.l}, theirs:</span> {summarise(kind, r.l, r.a)}
            </span>
            <span>
              <span className="font-medium">Yours:</span> {summarise(kind, r.l, r.b)}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => onResolve("theirs")} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium">
          Use their version (discard mine)
        </button>
        <button type="button" onClick={() => onResolve("mine")} className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white dark:text-background">
          Save mine on top of theirs
        </button>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ workflow actions
function ActionsPanel({ item, myId, flush }: { item: StudioItem; myId: string; flush: () => Promise<boolean> }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [result, setResult] = useState<Extract<ActionResult, { ok: false }> | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [level, setLevel] = useState("");
  const [correctedKey, setCorrectedKey] = useState("");
  const a = item.actions;
  const checklistDone = item.review_checklist.every((c) => checks[c]);

  function run(fn: () => Promise<ActionResult>, needsFlush = false) {
    setResult(null);
    start(async () => {
      if (needsFlush && !(await flush())) {
        setResult({ ok: false, error: "Save your changes before continuing." });
        return;
      }
      const res = await fn();
      if (res.ok) {
        setText("");
        router.refresh();
      } else setResult(res);
    });
  }

  const reasonNeeded = a.revise || a.quarantine || a.release || a.retire || a.set_access_tier || a.change_quarantine_level || a.correct_score || a.rollback || a.set_question_pool;
  const publishedOptions = ((item.published?.body as { options?: { id: string }[] } | undefined)?.options ?? []).map((o) => o.id);
  const commentNeeded = a.review || a.submit;
  const btn = "w-full rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50";
  const primary = `${btn} bg-accent text-white hover:bg-accent-strong dark:text-background`;
  const secondary = `${btn} border border-border bg-surface hover:border-accent`;
  const danger = `${btn} border border-danger/40 bg-surface text-danger hover:bg-danger-soft`;
  const short = text.trim().length < (a.review ? 3 : 5);

  return (
    <section className="space-y-3 rounded-xl border border-border bg-surface p-4" aria-labelledby="actions-heading">
      <h2 id="actions-heading" className="font-semibold">
        Next step
      </h2>
      {item.blockers.length > 0 && (
        <ul className="space-y-1 text-sm">
          {item.blockers.map((b, i) => (
            <li key={i} className="rounded-md bg-warn-soft px-2 py-1">
              {b}
            </li>
          ))}
        </ul>
      )}
      {a.review && item.review_checklist.length > 0 && (
        <fieldset className="space-y-1 rounded-lg border border-border p-2 text-sm">
          <legend className="px-1 font-medium">Checks before approving</legend>
          {item.review_checklist.map((c) => (
            <label key={c} className="flex items-center gap-2 capitalize">
              <input type="checkbox" checked={!!checks[c]} onChange={(e) => setChecks({ ...checks, [c]: e.target.checked })} />
              {c}
            </label>
          ))}
        </fieldset>
      )}
      {(a.quarantine || a.change_quarantine_level) && item.quarantine_levels.length > 0 && (
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Quarantine level</span>
          <select value={level} onChange={(e) => setLevel(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-2 py-1.5">
            <option value="">Choose…</option>
            <option value="SOFT">Soft: suspected defect, under review</option>
            <option value="VOID">Void: no valid answer</option>
            <option value="KEY_ERROR">Key error: published key is wrong</option>
          </select>
        </label>
      )}
      {(commentNeeded || reasonNeeded) && (
        <div className="space-y-1">
          <label htmlFor="action-text" className="text-sm font-medium">
            {a.review ? "Review comment" : a.submit ? "Note for the reviewer (optional)" : "Reason"}
          </label>
          <textarea id="action-text" value={text} onChange={(e) => setText(e.target.value)} rows={3} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
        </div>
      )}
      <div className="space-y-2">
        {a.submit && (
          <button type="button" className={primary} disabled={pending} onClick={() => run(() => submitItem(item.id, text.trim()), true)}>
            Submit for review
          </button>
        )}
        {a.withdraw && (
          <button type="button" className={secondary} disabled={pending} onClick={() => run(() => withdrawItem(item.id))}>
            Withdraw from review
          </button>
        )}
        {a.claim && (
          <button type="button" className={secondary} disabled={pending} onClick={() => run(() => claimItem(item.id, myId))}>
            Claim this review
          </button>
        )}
        {a.review && (
          <>
            <button type="button" className={primary} disabled={pending || short || !checklistDone} onClick={() => run(() => reviewItem(item.id, "approve", text.trim(), checks))}>
              Approve
            </button>
            <button type="button" className={secondary} disabled={pending || short} onClick={() => run(() => reviewItem(item.id, "request_changes", text.trim(), checks))}>
              Request changes
            </button>
          </>
        )}
        {a.publish && (
          <button type="button" className={primary} disabled={pending} onClick={() => run(() => publishItem(item.id))}>
            Publish to learners
          </button>
        )}
        {a.revise && (
          <button type="button" className={secondary} disabled={pending || short} onClick={() => run(() => reviseItem(item.id, text.trim()))}>
            Start a revision
          </button>
        )}
        {a.quarantine && (
          <button
            type="button"
            className={danger}
            disabled={pending || short || (item.quarantine_levels.length > 0 && !level)}
            onClick={() => run(() => quarantineItem(item.id, text.trim(), level || null))}
          >
            Quarantine (hide from learners)
          </button>
        )}
        {a.change_quarantine_level && (
          <button
            type="button"
            className={secondary}
            disabled={pending || short || !level || level === item.quarantine_level}
            onClick={() => run(() => quarantineItem(item.id, text.trim(), level))}
          >
            Change quarantine level
          </button>
        )}
        {a.correct_score && item.quarantine_level === "KEY_ERROR" && (
          <label className="block space-y-1 text-sm">
            <span className="font-medium">Corrected answer</span>
            <select value={correctedKey} onChange={(e) => setCorrectedKey(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-2 py-1.5">
              <option value="">Choose…</option>
              {publishedOptions.map((o, i) => (
                <option key={o} value={o}>
                  Option {String.fromCharCode(65 + i)}
                </option>
              ))}
            </select>
          </label>
        )}
        {a.correct_score && (
          <button
            type="button"
            className={danger}
            disabled={pending || text.trim().length < 10 || (item.quarantine_level === "KEY_ERROR" && !correctedKey)}
            onClick={() =>
              run(() =>
                recordScoreCorrection(item.id, item.quarantine_level === "KEY_ERROR" ? "KEY_ERROR" : "VOID", text.trim(), item.quarantine_level === "KEY_ERROR" ? correctedKey : null),
              )
            }
          >
            {item.quarantine_level === "KEY_ERROR" ? "Record key correction and re-score" : "Record void and re-score"}
          </button>
        )}
        {a.release && (
          <button type="button" className={secondary} disabled={pending || short} onClick={() => run(() => releaseItem(item.id, text.trim()))}>
            Release from quarantine
          </button>
        )}
        {a.rollback && (
          <button type="button" className={secondary} disabled={pending || short} onClick={() => run(() => rollbackItem(item.id, text.trim()))}>
            Roll back to the previous version
          </button>
        )}
        {a.set_question_pool && (
          <button
            type="button"
            className={secondary}
            disabled={pending || short}
            onClick={() => run(() => setQuestionPool(item.id, item.question_pool === "mock" ? "practice" : "mock", text.trim()))}
          >
            {item.question_pool === "mock" ? "Return to the practice pool" : "Reserve for mocks only"}
          </button>
        )}
        {a.set_access_tier && (
          <button
            type="button"
            className={secondary}
            disabled={pending || short}
            onClick={() => run(() => setAccessTier(item.id, item.access_tier === "preview" ? "premium" : "preview", text.trim()))}
          >
            {item.access_tier === "preview" ? "Make premium (plan or trial needed)" : "Make a free preview"}
          </button>
        )}
        {a.retire && (
          <button type="button" className={danger} disabled={pending || short} onClick={() => run(() => retireItem(item.id, text.trim()))}>
            Retire
          </button>
        )}
        {!Object.values(a).some(Boolean) && <p className="text-sm text-muted">No action is available to you at this stage.</p>}
      </div>
      {result && (
        <div role="alert" className="space-y-1 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm">
          <p>{result.error}</p>
          {result.errors && result.errors.length > 0 && (
            <ul className="list-disc pl-5">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function Feedback({ item }: { item: StudioItem }) {
  const reviews = item.working?.reviews ?? [];
  if (reviews.length === 0) return null;
  return (
    <section className="space-y-2 rounded-xl border border-border bg-surface p-4" aria-labelledby="feedback-heading">
      <h2 id="feedback-heading" className="font-semibold">
        Review feedback · version {item.working?.number}
      </h2>
      <ul className="space-y-2 text-sm">
        {reviews.map((r, i) => (
          <li key={i} className="rounded-lg bg-surface-muted p-2">
            <p className="font-medium">
              {r.decision === "approve" ? "Approved" : "Changes requested"} by {r.reviewer ?? "a reviewer"}
            </p>
            <p className="whitespace-pre-line">{r.comment}</p>
            <p className="text-xs text-muted">{when(r.created_at)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function History({ events }: { events: StudioHistoryEvent[] }) {
  return (
    <details className="rounded-xl border border-border bg-surface p-4">
      <summary className="cursor-pointer font-semibold">History ({events.length})</summary>
      <ol className="mt-3 space-y-2 text-sm">
        {events.map((e, i) => (
          <li key={i}>
            <span className="font-medium">{e.action.replace("content.", "").replaceAll("_", " ")}</span> by {e.actor ?? "system"}
            <span className="block text-xs text-muted">
              {when(e.at)}
              {typeof e.details.reason === "string" ? ` · ${e.details.reason}` : ""}
              {typeof e.details.version === "number" ? ` · version ${e.details.version}` : ""}
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}
