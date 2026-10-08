// Native written result (W06/W07): released teacher marks, honest completeness (no invented zeros), marking-guide
// corrections, learner actions on pending questions (a clearer copy, sent with one retry-safe key per photo, or
// "I didn't answer it"), a recheck request on the same evidence (no extra allowance) and a way to ask for help.
import * as ImagePicker from "expo-image-picker";
import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import type { WrittenResult } from "@portal/contracts";

import { Button, Choices, Field, FormError } from "@/components/form";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { api, ApiError } from "@/lib/api";

type Question = WrittenResult["questions"][number];
const marks = (u: number) => String(u / 100);
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const newKey = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
const CLASS_TEXT: Record<string, string> = {
  READABILITY: "A teacher used your clearer copy to mark this answer.",
  NEW_CONTENT: "Your copy showed new or changed work, so the original result stands.",
  INDETERMINATE: "The original was too unclear to compare with your copy, so the original result stands.",
};
const HISTORY: Record<string, string> = {
  initial: "first marking",
  recheck: "after recheck",
  completion: "after completing pending questions",
  regrade: "after a marking-guide correction",
};

export function WrittenResultView({ attemptId, token }: { attemptId: string; token: string }) {
  const req = useRequest((signal) => api.writtenResult(token, attemptId, signal), [token, attemptId]);
  if (req.state.status === "loading") return <Loading label="Loading your marks" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const r = req.state.data;
  if (r.status === "pending") {
    return <Notice title="Waiting for a teacher">Your script is in the marking queue. Marks appear here once a teacher releases them.</Notice>;
  }
  const awaiting = r.awaiting_regrade ?? [];
  return (
    <View style={{ gap: Space.md }}>
      <T variant="heading" accessibilityRole="header">
        Your marks
      </T>
      {r.completeness === "complete" ? (
        <T variant="title">
          {marks(r.total_units ?? 0)} / {marks(r.max_units)}
        </T>
      ) : (
        <Notice tone="warn" title={r.completeness === "partial_pending" ? "Marking isn't finished yet" : "Some questions couldn't be assessed"}>
          So far {marks(r.total_units ?? 0)} out of {marks(r.scored_max_units ?? 0)} on the questions a teacher marked. There is no final total until
          every question is resolved, and nothing is counted as zero just because it wasn&apos;t assessed.
        </Notice>
      )}
      <T variant="small">
        {awaiting.length
          ? `Marked by a teacher; question ${awaiting.join(", ")} is waiting to be re-marked under a corrected marking guide.`
          : r.decision_method === "SYSTEM" && r.history.at(-1)?.case_kind === "regrade"
            ? "Marked by a teacher; carried forward unchanged after a marking-guide correction."
            : r.completeness === "complete"
              ? "Marked by a teacher."
              : "Reviewed by a teacher so far."}
      </T>
      {(r.notices ?? []).map((n) => (
        <Notice key={`${n.kind}:${n.created_at}`} title="Marking guide corrected">
          {n.message}
        </Notice>
      ))}
      {r.questions.map((q) => (
        <Card key={q.position}>
          <View style={{ gap: Space.xs }}>
            <T style={{ fontWeight: "600" }}>
              Question {q.position}:{" "}
              {q.status === "scored" ? `${marks(q.earned_units ?? 0)} / ${marks(q.max_units)}` : q.status === "pending" ? "pending" : "couldn't be assessed"}
            </T>
            {q.status !== "scored" && (
              <T variant="small">
                {q.status_reason}
                {q.status === "unavailable" ? " The allowance for this question was returned to your plan." : ""}
              </T>
            )}
            {q.criteria.map((cr) => (
              <T key={cr.id} variant="small">
                {marks(cr.earned_units)} / {marks(cr.max_units)} · {cr.description}
                {cr.reason ? ` — ${cr.reason}` : ""}
              </T>
            ))}
            <PendingAction attemptId={attemptId} token={token} q={q} onDone={req.retry} />
            <Button
              variant="secondary"
              label="Report a problem with this question"
              onPress={() => router.push({ pathname: "/help", params: { attempt: attemptId, position: String(q.position) } })}
            />
          </View>
        </Card>
      ))}
      {r.history.length > 1 && (
        <Card>
          <T style={{ fontWeight: "600" }}>Mark history</T>
          {r.history.map((h) => (
            <T key={h.version} variant="small">
              Version {h.version}: {marks(h.total_units)} · {HISTORY[h.case_kind] ?? h.case_kind} · released {when(h.released_at)}
            </T>
          ))}
        </Card>
      )}
      <Recheck attemptId={attemptId} token={token} r={r} onDone={req.retry} />
    </View>
  );
}

function PendingAction({ attemptId, token, q, onDone }: { attemptId: string; token: string; q: Question; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const open = q.status === "pending" && q.learner_action && q.action_deadline && new Date(q.action_deadline) > new Date();

  async function send() {
    setError(null);
    setNote(null);
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.9,
      preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
    });
    if (res.canceled) return;
    setBusy(true);
    const key = newKey(); // one key per chosen photo: a retried send returns the original acknowledgement
    try {
      const blob = await (await fetch(res.assets[0].uri)).blob();
      let out;
      try {
        out = await api.rescan(token, attemptId, q.position, blob, key);
      } catch (e) {
        if (!(e instanceof ApiError) || e.kind !== "offline") throw e;
        out = await api.rescan(token, attemptId, q.position, blob, key); // one retry with the same key
      }
      if (out.replay) setNote("This copy was already received. Nothing more to do.");
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That didn't upload.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.confirmUnanswered(token, attemptId, q.position);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't confirm.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: Space.xs }}>
      {(q.revisions ?? []).map((rv) => (
        <T key={rv.id} variant="small">
          Clearer copy sent {when(rv.created_at)}: {rv.classification ? CLASS_TEXT[rv.classification] : "waiting for a teacher to compare it with your original."}
        </T>
      ))}
      {open && (
        <Notice tone="warn" title={`Action for question ${q.position}`}>
          {q.learner_action === "confirm_or_rescan"
            ? "This answer looks blank to the teacher. Send a clearer photo of it, or tell us you didn't answer it."
            : "The teacher couldn't read this answer. Send a clearer photo of the same page (not a new answer)."}{" "}
          Please act by {when(q.action_deadline!)}; after that the question is left unmarked and its allowance returned.
        </Notice>
      )}
      {open && <Button label="Send a clearer photo" onPress={() => void send()} busy={busy} />}
      {open && q.learner_action === "confirm_or_rescan" && (
        <Button variant="secondary" label="I didn't answer this question" onPress={() => void confirm()} busy={busy} />
      )}
      {note && <T variant="small">{note}</T>}
      <FormError message={error} />
    </View>
  );
}

function Recheck({ attemptId, token, r, onDone }: { attemptId: string; token: string; r: WrittenResult; onDone: () => void }) {
  const rc = r.recheck;
  const [picked, setPicked] = useState<number[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (rc.status === "requested") {
    return <Notice title="Recheck requested">A different teacher will look at question {rc.positions.join(", ")} again. It doesn&apos;t use more allowance.</Notice>;
  }
  if (rc.status !== "available" || rc.eligible_positions.length === 0) return null;

  async function ask() {
    setBusy(true);
    setError(null);
    try {
      await api.requestRecheck(token, attemptId, reason.trim(), picked);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't request a recheck.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <View style={{ gap: Space.sm }}>
        <T style={{ fontWeight: "600" }}>Ask for a recheck</T>
        <T variant="small">
          A different teacher marks the same answer again. It doesn&apos;t use more allowance{rc.window_ends_at ? `; ask by ${when(rc.window_ends_at)}` : ""}.
        </T>
        <Choices
          label="Which questions?"
          options={rc.eligible_positions.map((p) => [p, `Question ${p}`] as const)}
          selected={picked}
          onToggle={(p) => setPicked((s) => (s.includes(p) ? s.filter((x) => x !== p) : [...s, p]))}
        />
        <Field label="Why should it be marked again?" value={reason} onChangeText={setReason} multiline maxLength={2000} />
        <FormError message={error} />
        <Button label="Request recheck" onPress={() => void ask()} busy={busy} disabled={picked.length === 0 || reason.trim().length < 10} />
      </View>
    </Card>
  );
}
