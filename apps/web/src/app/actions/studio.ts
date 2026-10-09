"use server";

// Studio mutations. Server Actions are POST-only with an Origin check (CSRF); the API re-checks every permission,
// scope, independence rule and publication gate, so nothing here is a security boundary on its own.
import { redirect } from "next/navigation";
import type { Problem, StudioItem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

type ProblemWithExtras = Problem & { warnings?: string[]; current?: ConflictState; errors?: unknown };

export type ConflictState = {
  revision: number;
  title: string;
  body: Record<string, unknown>;
  source_refs: SourceRef[];
  updated_at: string;
  updated_by: string | null;
};
export type Block = { type: string; [key: string]: unknown };
export type SourceRef = { source_document_id: string; pdf_from: number; pdf_to: number; note?: string | null };

export type ActionResult =
  | { ok: true; item: StudioItem }
  | { ok: false; error: string; errors?: string[]; warnings?: string[]; conflict?: ConflictState };

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio");
  return t;
}

function messages(errors: unknown): string[] {
  if (!Array.isArray(errors)) return [];
  return errors.map((e) =>
    typeof e === "string"
      ? e
      : typeof e === "object" && e && "msg" in e
        ? `${String((e as { loc?: unknown[] }).loc?.slice(1).join(".") ?? "")}: ${String((e as { msg: unknown }).msg)}`
        : String(e),
  );
}

async function call(path: string, method: "POST" | "PUT", body?: unknown): Promise<ActionResult> {
  const res = await api<StudioItem>(path, { method, token: await token(), body: JSON.stringify(body ?? {}) });
  if (res.ok) return { ok: true, item: res.data };
  if (res.status === 401) redirect("/signin?next=/studio");
  const p = res.problem as ProblemWithExtras | null;
  return {
    ok: false,
    error: p?.detail ?? `The request failed (${res.status}).`,
    errors: messages(p?.errors),
    warnings: p?.warnings,
    conflict: res.status === 409 ? p?.current : undefined,
  };
}

const item = (id: string, action: string) => `/v1/studio/items/${encodeURIComponent(id)}/${action}`;

export async function createItem(_prev: unknown, form: FormData): Promise<{ error?: string } | undefined> {
  const raw = String(form.get("kind") ?? "lesson");
  const kind = raw === "mcq" || raw === "written" || raw === "storyboard" ? raw : "lesson";
  const chapter_id = String(form.get("chapter_id") ?? "");
  const topic_id = String(form.get("topic_id") ?? "") || null;
  const title = String(form.get("title") ?? "").trim();
  if (!chapter_id) return { error: "Choose a chapter." };
  if (title.length < 3) return { error: "Give it a title of at least 3 characters." };
  const res = await call("/v1/studio/items", "POST", { kind, chapter_id, topic_id, title });
  if (!res.ok) return { error: [res.error, ...(res.errors ?? [])].join(" ") };
  redirect(`/studio/items/${res.item.id}`);
}

export async function saveDraft(
  id: string,
  revision: number,
  title: string,
  body: Record<string, unknown>,
  sourceRefs: SourceRef[],
): Promise<ActionResult> {
  return call(item(id, "draft"), "PUT", { revision, title, body, source_refs: sourceRefs });
}

export async function submitItem(id: string, note: string): Promise<ActionResult> {
  return call(item(id, "submit"), "POST", { note: note || null });
}
export async function withdrawItem(id: string): Promise<ActionResult> {
  return call(item(id, "withdraw"), "POST");
}
export async function claimItem(id: string, myId: string): Promise<ActionResult> {
  return call(item(id, "assign"), "POST", { reviewer_id: myId });
}
export async function reviewItem(
  id: string,
  decision: "approve" | "request_changes",
  comment: string,
  checklist: Record<string, boolean> = {},
): Promise<ActionResult> {
  return call(item(id, "review"), "POST", { decision, comment, checklist });
}
export async function publishItem(id: string): Promise<ActionResult> {
  return call(item(id, "publish"), "POST");
}
export async function reviseItem(id: string, reason: string): Promise<ActionResult> {
  return call(item(id, "revise"), "POST", { reason });
}
export async function quarantineItem(id: string, reason: string, level: string | null = null): Promise<ActionResult> {
  return call(item(id, "quarantine"), "POST", { reason, level });
}
/** §5.7: a reviewed VOID or KEY_ERROR correction; the API re-scores affected attempts as new score versions. */
export async function recordScoreCorrection(id: string, defect: "VOID" | "KEY_ERROR", reason: string, correctedOptionId: string | null): Promise<ActionResult> {
  return call(item(id, "score-corrections"), "POST", { defect, reason, corrected_option_id: correctedOptionId });
}
/** P06.S3.T3: put the previously published version back (history is kept; audited). */
export async function rollbackItem(id: string, reason: string): Promise<ActionResult> {
  return call(item(id, "rollback"), "POST", { reason });
}
/** P08.S3.T3: reserve a question for mocks (never in practice tests) or return it to practice. */
export async function setQuestionPool(id: string, pool: "practice" | "mock", reason: string): Promise<ActionResult> {
  return call(item(id, "question-pool"), "POST", { pool, reason });
}
export async function releaseItem(id: string, reason: string): Promise<ActionResult> {
  return call(item(id, "release"), "POST", { reason });
}
export async function setAccessTier(id: string, tier: "preview" | "premium", reason: string): Promise<ActionResult> {
  return call(item(id, "access-tier"), "POST", { tier, reason });
}
export async function retireItem(id: string, reason: string): Promise<ActionResult> {
  return call(item(id, "retire"), "POST", { reason });
}

export async function createRubric(questionId: string, title: string): Promise<{ error?: string } | undefined> {
  const res = await call("/v1/studio/items", "POST", {
    kind: "rubric",
    parent_item_id: questionId, // a rubric lives with its question; the API takes the chapter from it
    title: `Rubric: ${title}`.slice(0, 200),
  });
  if (!res.ok) return { error: [res.error, ...(res.errors ?? [])].join(" ") };
  redirect(`/studio/items/${res.item.id}`);
}

/** P07.S1.T2: start a language variant of this lesson concept (its own draft, its own review). */
export async function createLanguageVariant(
  lessonId: string,
  title: string,
  language: string,
  origin: string,
): Promise<{ error?: string } | undefined> {
  const res = await call("/v1/studio/items", "POST", { kind: "lesson", translation_of: lessonId, language, translation_origin: origin, title: title.slice(0, 200) });
  if (!res.ok) return { error: [res.error, ...(res.errors ?? [])].join(" ") };
  redirect(`/studio/items/${res.item.id}`);
}
