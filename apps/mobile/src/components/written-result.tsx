// Native written result (W06/W07): released teacher marks, honest completeness (no invented zeros), marking-guide
// corrections, learner actions on pending questions (a clearer copy, sent with one retry-safe key per photo, or
// "I didn't answer it"), a recheck request on the same evidence (no extra allowance) and a way to ask for help.
import * as ImagePicker from "expo-image-picker";
import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import type { WrittenResult } from "@portal/contracts";

import { Button, Choices, Field, FormError } from "@/components/form";
import { LessonBlocks } from "@/components/lesson-blocks";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { api, ApiError } from "@/lib/api";
import { TIME_ZONE } from "@/lib/dates";

type Question = WrittenResult["questions"][number];
const marks = (u: number) => String(u / 100);
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });
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

// RESULT-ARITHMETIC-01 (§20.9.3, W07.S1.T1): marks on the scored questions, marks still being marked and marks that
// couldn't be assessed, side by side; they add up to the whole test. No total or percentage for an incomplete paper.
function PartialMarks({ r }: { r: WrittenResult }) {
  const scored = r.scored_max_units ?? 0;
  const pending = r.pending_max_units ?? 0;
  const unavailable = r.unavailable_max_units ?? 0;
  const stillMarking = r.completeness === "partial_pending";
  return (
    <Notice tone="warn" title={stillMarking ? "Marking isn't finished yet" : "Some questions couldn't be assessed"}>
      {scored > 0 ? `${marks(r.total_units ?? 0)} out of ${marks(scored)} on the questions a teacher marked.` : "No question has been marked yet."}
      {`\nMarked: ${marks(scored)} marks`}
      {pending > 0 ? `\nStill being marked: ${marks(pending)} marks` : ""}
      {unavailable > 0 ? `\nCouldn't be assessed: ${marks(unavailable)} marks` : ""}
      {`\nWhole test: ${marks(r.max_units)} marks\n`}
      {stillMarking
        ? "There is no final total until every question is resolved, and nothing is counted as zero just because it wasn't assessed."
        : "This test has no final total or percentage, because some questions couldn't be assessed. They aren't counted as zero."}
    </Notice>
  );
}

// §20.9.3: what is happening to the script now, kept apart from the marks.
function WorkStatus({ status }: { status: WrittenResult["work_status"] }) {
  if (status === "action_required") return <T variant="small">Your step: a teacher asked you for something on a question below.</T>;
  if (status === "delayed") return <T variant="small">Marking is taking longer than planned. Your script is still in the queue, and nothing has been lost.</T>;
  if (status === "in_review") return <T variant="small">A teacher is still working on this script.</T>;
  return null;
}

export function WrittenResultView({ attemptId, token }: { attemptId: string; token: string }) {
  const req = useRequest((signal) => api.writtenResult(token, attemptId, signal), [token, attemptId]);
  if (req.state.status === "loading") return <Loading label="Loading your marks" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={req.retry} />;
  const r = req.state.data;
  if (r.status === "pending") {
    return (
      <Notice title="Waiting for a teacher">
        Your script is in the marking queue. Marks appear here once a teacher releases them.
        {r.work_status === "delayed" ? " Marking is taking longer than planned; nothing has been lost." : ""}
      </Notice>
    );
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
      ) : r.assessment_state === "unavailable" ? (
        // COMPLETENESS-01 (§20.9.3): nothing could be assessed, so there is no mark at all, not a zero.
        <Notice tone="warn" title="No mark for this test">
          None of the questions could be assessed, so this test has no mark. The allowance it used was returned; the reasons are shown with each
          question below.
        </Notice>
      ) : (
        <PartialMarks r={r} />
      )}
      <WorkStatus status={r.work_status} />
      <T variant="small">
        {awaiting.length
          ? `Marked by a teacher; question ${awaiting.join(", ")} is waiting to be re-marked under a corrected marking guide.`
          : r.decision_method === "SYSTEM" && r.versions.at(-1)?.case_kind === "regrade"
            ? "Marked by a teacher; carried forward unchanged after a marking-guide correction."
            : r.completeness === "complete"
              ? "Marked by a teacher."
              : r.assessment_method === "none"
                ? "No question has been marked yet."
                : "Marked by a teacher: only the questions that have a mark."}
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
            {q.academic_review === "open" && (
              // ACADEMIC-REVIEW-01: the guide doesn't cover the method yet; no score is forced meanwhile.
              <T variant="small">
                A senior subject reviewer is checking how the marking guide applies to your answer. This question has no mark until then, and nothing is
                counted as zero.
              </T>
            )}
            {q.criteria.map((cr) => (
              <T key={cr.id} variant="small">
                {marks(cr.earned_units)} / {marks(cr.max_units)} · {cr.description}
                {cr.reason ? ` — ${cr.reason}` : ""}
                {/* FEEDBACK-EVIDENCE-01: the place on the script the comment is about, in words. */}
                {(cr.evidence ?? []).map((e) => (e.available ? ` (see ${e.where})` : ` (about ${e.where}: that scan is no longer available)`)).join("")}
              </T>
            ))}
            {q.next_steps && (
              // NEXT-STEPS-01: the rubric's own words and reviewed lessons; nothing generated.
              <View style={{ gap: 2 }} accessibilityLabel="Next steps">
                <T variant="small" style={{ fontWeight: "600" }}>
                  Next steps
                </T>
                {q.next_steps.focus.map((f) => (
                  <T key={f.criterion_id} variant="small">
                    Work on: {f.description}
                    {f.common_mistakes.length ? ` (common mistakes: ${f.common_mistakes.join("; ")})` : ""}
                  </T>
                ))}
                {q.next_steps.lessons.map((l) => (
                  <Button key={l.id} variant="link" label={`Revise: ${l.title}`} onPress={() => router.push({ pathname: "/chapter/[id]", params: { id: l.chapter_id } })} />
                ))}
                {q.next_steps.lessons_missing && <T variant="small">No reviewed lesson is published for this topic yet.</T>}
              </View>
            )}
            {/* MODEL-ANSWER-01 (W07.S1.T3): released with the mark, from the marking guide that marked it. */}
            {q.model_answer && q.model_answer.length > 0 ? (
              <View style={{ gap: Space.xs }}>
                <T style={{ fontWeight: "600" }}>Worked answer</T>
                {q.model_answer_note ? <T variant="small">{q.model_answer_note}</T> : null}
                <LessonBlocks blocks={q.model_answer as { type: string }[]} />
              </View>
            ) : null}
            <PendingAction attemptId={attemptId} token={token} q={q} onDone={req.retry} />
            <Button
              variant="secondary"
              label="Report a problem with this question"
              onPress={() => router.push({ pathname: "/help", params: { attempt: attemptId, position: String(q.position) } })}
            />
          </View>
        </Card>
      ))}
      {r.versions.length > 1 && (
        <Card>
          <T style={{ fontWeight: "600" }}>Mark history</T>
          {r.versions.map((h, i) => {
            // HISTORY-01 (W07.S2.T2): what each version used and why a question changed.
            const before = i > 0 ? r.versions[i - 1] : null;
            const mark = (q: (typeof h.questions)[number] | undefined) =>
              !q || q.status === "pending" ? "pending" : q.status === "unavailable" ? "couldn't be assessed" : marks(q.earned_units ?? 0);
            const guides = [...new Set(h.questions.map((q) => q.rubric_version).filter((x): x is number => x !== null))].sort((a, b) => a - b);
            const extra = [h.labels.includes("clearer_copy") ? "marked from a clearer copy you sent" : null, h.labels.includes("deadline_passed") ? "a deadline passed" : null]
              .filter(Boolean)
              .map((l) => ` · ${l}`)
              .join("");
            return (
              <View key={h.version} style={{ gap: Space.xs }}>
                <T variant="small">
                  Version {h.version}: {h.total_units === null ? "no mark" : marks(h.total_units)} · {HISTORY[h.case_kind] ?? h.case_kind}
                  {extra}
                  {guides.length ? ` · marking guide v${guides.join(", v")}` : ""} · released {when(h.released_at)}
                </T>
                {h.questions
                  .filter((q) => q.reason)
                  .map((q) => (
                    <T key={q.position} variant="small">
                      {"  "}Question {q.position}
                      {q.changed ? `: ${mark(before?.questions.find((p) => p.position === q.position))} → ${mark(q)}` : ""} — {q.reason}
                    </T>
                  ))}
              </View>
            );
          })}
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
