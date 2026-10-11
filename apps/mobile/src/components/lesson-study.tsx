// Study tools on native (STUDY-TOOLS-01) and lesson completion (LESSON-DONE-01): the same rules as the web. A note being
// written is kept on the device until the server confirms it; if it changed or was deleted on another device, the
// learner sees both and chooses. Nothing is merged or overwritten silently.
import type { StudyNote } from "@portal/contracts";
import { useEffect, useState } from "react";
import { Pressable, View } from "react-native";

import { Button, Field, FormError } from "@/components/form";
import { T } from "@/components/ui";
import { Radius, Space } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { readDraft, writeDraft } from "@/lib/note-drafts";

type Conflict = { reason: "NOTE_CHANGED" | "NOTE_DELETED"; current: StudyNote };

function conflictOf(e: unknown): Conflict | null {
  if (!(e instanceof ApiError) || e.kind !== "conflict") return null;
  const p = e.problem as { code_reason?: string; current?: StudyNote } | null | undefined;
  if ((p?.code_reason === "NOTE_CHANGED" || p?.code_reason === "NOTE_DELETED") && p.current) return { reason: p.code_reason, current: p.current };
  return null;
}

export function LessonNote({ token, lessonId }: { token: string; lessonId: string }) {
  const c = useTheme();
  const { state: auth } = useAuth();
  const owner = auth.status === "signed_in" ? auth.me.id : ""; // ISOLATION-01: drafts are kept per account
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [saved, setSaved] = useState("");
  const [base, setBase] = useState(0);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<Conflict | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const n = await api.note(token, lessonId);
        const draft = await readDraft(owner, lessonId);
        if (!live) return;
        const current = n.deleted ? "" : n.text;
        setSaved(current);
        setBase(n.revision);
        if (draft && draft.text !== current) {
          setText(draft.text); // an unsent edit from earlier on this device
          setBase(draft.base);
          setOpen(true);
        } else {
          setText(current);
          setOpen(current !== "");
        }
      } catch {
        /* note unavailable (e.g. lesson not readable): no editor */
      } finally {
        if (live) setLoaded(true);
      }
    })();
    return () => {
      live = false;
    };
  }, [token, lessonId, owner]);

  async function save(value: string, from: number) {
    setBusy(true);
    setError(null);
    await writeDraft(owner, lessonId, { text: value, base: from });
    try {
      const n = await api.saveNote(token, lessonId, value, from);
      setBase(n.revision);
      setSaved(n.text);
      setText(n.text);
      setConflict(null);
      setStatus("Saved. Only you can see this note.");
      await writeDraft(owner, lessonId, null);
    } catch (e) {
      const k = conflictOf(e);
      if (k) setConflict(k);
      else setError(e instanceof ApiError && e.kind === "offline" ? "You're offline. Your note is kept on this device; save again when you're back online." : e instanceof ApiError ? e.message : "Couldn't save your note.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      const n = await api.deleteNote(token, lessonId, base);
      setBase(n.revision);
      setSaved("");
      setText("");
      setStatus("Note deleted.");
    } catch (e) {
      const k = conflictOf(e);
      if (k) setConflict(k);
      else setError(e instanceof ApiError ? e.message : "Couldn't delete your note.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return null;
  if (!open) return <Button variant="link" label="Add a private note" onPress={() => setOpen(true)} />;
  return (
    <View style={{ gap: Space.sm, padding: Space.md, borderRadius: Radius.sm, backgroundColor: c.surfaceMuted }}>
      <Field
        label="My private note"
        value={text}
        multiline
        maxLength={5000}
        onChangeText={(v) => {
          setText(v);
          setStatus(null);
          void writeDraft(owner, lessonId, { text: v, base });
        }}
      />
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Space.sm, alignItems: "center" }}>
        <Button label="Save note" busy={busy} disabled={text === saved || !!conflict} onPress={() => void save(text, base)} />
        {saved !== "" && <Button variant="link" label="Delete note" disabled={busy} onPress={() => void remove()} />}
      </View>
      {status && text === saved && (
        <T variant="small" accessibilityLiveRegion="polite">
          {status}
        </T>
      )}
      {text !== saved && !conflict && <T variant="small">Not saved yet (kept on this device).</T>}
      <FormError message={error} />
      {conflict && (
        <View accessibilityRole="alert" style={{ gap: Space.sm, padding: Space.md, borderRadius: Radius.sm, borderWidth: 1, borderColor: c.warn, backgroundColor: c.warnSoft }}>
          <T style={{ fontWeight: "600" }}>{conflict.reason === "NOTE_DELETED" ? "You deleted this note on another device." : "This note changed on another device:"}</T>
          {conflict.reason === "NOTE_CHANGED" && <T>{conflict.current.text}</T>}
          <Button label="Keep mine" busy={busy} onPress={() => void save(text, conflict.current.revision)} />
          <Button
            variant="secondary"
            label={conflict.reason === "NOTE_DELETED" ? "Discard mine" : "Use the other version"}
            onPress={() => {
              const other = conflict.current.deleted ? "" : conflict.current.text;
              setText(other);
              setSaved(other);
              setBase(conflict.current.revision);
              setConflict(null);
              void writeDraft(owner, lessonId, null);
            }}
          />
        </View>
      )}
    </View>
  );
}

export function CompletionToggle({ token, lessonId, done, onChange }: { token: string; lessonId: string; done: boolean; onChange: (done: boolean) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <View style={{ gap: Space.xs }}>
      <Button
        variant="secondary"
        busy={busy}
        label={done ? "✓ Completed: undo" : "Mark as completed"}
        onPress={async () => {
          setBusy(true);
          setError(null);
          try {
            await api.setCompleted(token, lessonId, !done);
            onChange(!done);
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Couldn't change this.");
          } finally {
            setBusy(false);
          }
        }}
      />
      <T variant="small">Completion tracks your reading only. It isn&apos;t evidence of what you know.</T>
      <FormError message={error} />
    </View>
  );
}

export function SaveFormula({ token, lessonId, index }: { token: string; lessonId: string; index: number }) {
  const [state, setState] = useState<"idle" | "busy" | "saved" | "error">("idle");
  return (
    <View style={{ alignItems: "flex-end" }}>
      <Button
        variant="link"
        busy={state === "busy"}
        disabled={state === "saved"}
        label={state === "saved" ? "Saved to your formulas" : state === "error" ? "Couldn't save. Try again" : "Save formula"}
        onPress={async () => {
          setState("busy");
          try {
            await api.saveFormula(token, lessonId, index);
            setState("saved");
          } catch {
            setState("error");
          }
        }}
      />
    </View>
  );
}

export function FavouriteStar({ token, topicId, label, initial }: { token: string; topicId: string; label: string; initial: boolean }) {
  const c = useTheme();
  const [on, setOn] = useState(initial);
  const [busy, setBusy] = useState(false);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${on ? "Remove from" : "Add to"} favourites: ${label}`}
      aria-pressed={on}
      disabled={busy}
      hitSlop={8}
      onPress={async () => {
        setBusy(true);
        setOn(!on);
        try {
          await api.setFavourite(token, topicId, !on);
        } catch {
          setOn(on);
        } finally {
          setBusy(false);
        }
      }}>
      <T style={{ fontSize: 20, color: on ? c.warn : c.muted }}>{on ? "★" : "☆"}</T>
    </Pressable>
  );
}
