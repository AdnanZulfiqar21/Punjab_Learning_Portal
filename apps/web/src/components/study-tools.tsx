"use client";

// P11.S2.T2 (STUDY-TOOLS-01): personal study tools on the lesson page. A note being written is kept on this device
// until the server confirms it; if it changed or was deleted on another device, the learner sees both and chooses.
import { useEffect, useId, useState } from "react";
import type { StudyNote } from "@portal/contracts";
import { deleteNote, saveFormula, saveNote, setFavourite, type NoteResult } from "@/app/actions/study";

type Draft = { text: string; base: number };
const draftKey = (lessonId: string) => `portal-note-draft:${lessonId}`;

function readDraft(lessonId: string): Draft | null {
  try {
    const raw = window.localStorage.getItem(draftKey(lessonId));
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null; // storage unavailable: the note still saves; it just isn't kept across a reload while offline
  }
}

function writeDraft(lessonId: string, d: Draft | null) {
  try {
    if (d) window.localStorage.setItem(draftKey(lessonId), JSON.stringify(d));
    else window.localStorage.removeItem(draftKey(lessonId));
  } catch {
    /* see readDraft */
  }
}

type Status =
  | { kind: "idle" | "saving" | "saved" | "deleted" }
  | { kind: "error"; message: string }
  | { kind: "conflict"; reason: "NOTE_CHANGED" | "NOTE_DELETED"; current: StudyNote };

export function LessonNote({ lessonId, initial }: { lessonId: string; initial: StudyNote }) {
  const id = useId();
  const [text, setText] = useState(initial.deleted ? "" : initial.text);
  const [base, setBase] = useState(initial.revision);
  const [saved, setSaved] = useState(initial.deleted ? "" : initial.text);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [open, setOpen] = useState(!initial.deleted && initial.text !== "");

  // An unsent draft from an earlier visit on this device (e.g. written offline) is restored and marked unsaved.
  useEffect(() => {
    const d = readDraft(lessonId);
    if (d && d.text !== (initial.deleted ? "" : initial.text)) {
      setText(d.text); // eslint-disable-line react-hooks/set-state-in-effect -- restoring device storage after hydration
      setBase(d.base);
      setOpen(true);
    }
  }, [lessonId, initial]);

  function apply(r: NoteResult, after: "saved" | "deleted") {
    if (r.ok) {
      setBase(r.note.revision);
      setSaved(r.note.text);
      setText(r.note.text);
      writeDraft(lessonId, null);
      setStatus({ kind: after });
    } else if (r.conflict) {
      setStatus({ kind: "conflict", reason: r.conflict, current: r.current });
    } else {
      setStatus({ kind: "error", message: r.message });
    }
  }

  async function save(value: string, from: number) {
    setStatus({ kind: "saving" });
    writeDraft(lessonId, { text: value, base: from });
    try {
      apply(await saveNote(lessonId, value, from), "saved");
    } catch {
      setStatus({ kind: "error", message: "You're offline. Your note is kept on this device; save again when you're back online." });
    }
  }

  async function remove() {
    setStatus({ kind: "saving" });
    try {
      apply(await deleteNote(lessonId, base), "deleted");
    } catch {
      setStatus({ kind: "error", message: "You're offline. Try deleting again when you're back online." });
    }
  }

  function takeOther(current: StudyNote) {
    setText(current.deleted ? "" : current.text);
    setSaved(current.deleted ? "" : current.text);
    setBase(current.revision);
    writeDraft(lessonId, null);
    setStatus({ kind: "idle" });
  }

  const dirty = text !== saved;
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="text-sm text-accent underline-offset-2 hover:underline">
        Add a private note
      </button>
    );
  }
  return (
    <div className="space-y-2 rounded-lg border border-border bg-surface-muted p-3 text-sm">
      <label htmlFor={id} className="font-medium">
        My private note
      </label>
      <textarea
        id={id}
        value={text}
        maxLength={5000}
        rows={3}
        onChange={(e) => {
          setText(e.target.value);
          writeDraft(lessonId, { text: e.target.value, base });
          if (status.kind !== "conflict") setStatus({ kind: "idle" });
        }}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2"
      />
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={!dirty || status.kind === "saving" || status.kind === "conflict"}
          onClick={() => void save(text, base)}
          className="rounded-lg bg-accent px-3 py-1.5 font-medium text-white disabled:opacity-50 dark:text-background"
        >
          Save note
        </button>
        {saved !== "" && (
          <button type="button" disabled={status.kind === "saving"} onClick={() => void remove()} className="text-accent underline-offset-2 hover:underline">
            Delete note
          </button>
        )}
        <span role="status" aria-live="polite" className="text-muted">
          {status.kind === "saving" && "Saving…"}
          {status.kind === "saved" && !dirty && "Saved. Only you can see this note."}
          {status.kind === "deleted" && "Note deleted."}
          {status.kind === "idle" && dirty && "Not saved yet (kept on this device)."}
        </span>
      </div>
      {status.kind === "error" && (
        <p role="alert" className="text-danger">
          {status.message}
        </p>
      )}
      {status.kind === "conflict" && (
        <div role="alert" className="space-y-2 rounded-lg border border-warn bg-warn-soft p-3">
          {status.reason === "NOTE_DELETED" ? (
            <p className="font-medium">You deleted this note on another device.</p>
          ) : (
            <>
              <p className="font-medium">This note changed on another device:</p>
              <p className="whitespace-pre-wrap rounded border border-border bg-surface px-2 py-1">{status.current.text}</p>
            </>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => void save(text, status.current.revision)} className="rounded-lg bg-accent px-3 py-1.5 font-medium text-white dark:text-background">
              Keep mine
            </button>
            <button type="button" onClick={() => takeOther(status.current)} className="rounded-lg border border-border bg-surface px-3 py-1.5">
              {status.reason === "NOTE_DELETED" ? "Discard mine" : "Use the other version"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function FavouriteButton({ topicId, label, initial }: { topicId: string; label: string; initial: boolean }) {
  const [on, setOn] = useState(initial);
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={`${on ? "Remove from" : "Add to"} favourites: ${label}`}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        const next = !on;
        setOn(next);
        const r = await setFavourite(topicId, next).catch(() => ({ ok: false }));
        if (!r.ok) setOn(!next);
        setBusy(false);
      }}
      className={`shrink-0 rounded-md px-2 py-1 text-lg leading-none ${on ? "text-warn" : "text-muted hover:text-accent"}`}
    >
      {on ? "★" : "☆"}
    </button>
  );
}

export function SaveFormulaButton({ lessonId, index }: { lessonId: string; index: number }) {
  const [state, setState] = useState<"idle" | "busy" | "saved" | "error">("idle");
  return (
    <div className="-mt-2 text-right text-sm">
      <button
        type="button"
        disabled={state === "busy" || state === "saved"}
        onClick={async () => {
          setState("busy");
          const r = await saveFormula(lessonId, index).catch(() => ({ ok: false }));
          setState(r.ok ? "saved" : "error");
        }}
        className="text-accent underline-offset-2 hover:underline disabled:text-muted disabled:no-underline"
      >
        {state === "saved" ? "Saved to your formulas" : "Save formula"}
      </button>
      {state === "error" && (
        <span role="alert" className="ml-2 text-danger">
          Couldn&apos;t save. Try again.
        </span>
      )}
    </div>
  );
}
