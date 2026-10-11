"use server";

// P05.S1.T2 (CONCEPTS-01): learning concepts, their topics and prerequisites. The API enforces scope, the frozen state
// of published concepts and the independent-reviewer rule; these actions only forward.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type ConceptResult = { ok: true; id?: string } | { ok: false; error: string; errors?: string[] };

async function call(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<ConceptResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/concepts");
  const res = await api<{ id?: string }>(path, { method, token: t, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  revalidatePath("/studio/concepts", "layout");
  if (res.ok) return { ok: true, id: res.data?.id };
  const p = res.problem as (Problem & { errors?: unknown[] }) | null;
  const errors = Array.isArray(p?.errors) ? p.errors.map((e) => (typeof e === "string" ? e : String((e as { msg?: string }).msg ?? JSON.stringify(e)))) : undefined;
  return { ok: false, error: p?.detail ?? `The request failed (${res.status}).`, errors };
}

const concept = (id: string, part = "") => `/v1/studio/concepts/${encodeURIComponent(id)}${part}`;

export async function createConcept(form: FormData): Promise<ConceptResult> {
  return call("/v1/studio/concepts", "POST", {
    code: String(form.get("code") ?? "").trim().toLowerCase(),
    title: String(form.get("title") ?? "").trim(),
    statement: String(form.get("statement") ?? "").trim(),
    subject: String(form.get("subject") ?? "biology"),
  });
}

export async function updateConcept(
  id: string,
  body: { title?: string; statement?: string; source_refs?: { source_document_id: string; pdf_from: number; pdf_to: number }[] },
): Promise<ConceptResult> {
  return call(concept(id), "PUT", body);
}

export async function mapTopics(id: string, topicIds: string[]): Promise<ConceptResult> {
  return call(concept(id, "/topics"), "PUT", { topic_ids: topicIds });
}

export async function addPrerequisite(id: string, requiresId: string, bridgingLessonId?: string): Promise<ConceptResult> {
  return call(concept(id, "/prerequisites"), "POST", { requires_id: requiresId, ...(bridgingLessonId ? { bridging_lesson_id: bridgingLessonId } : {}) });
}

export async function removePrerequisite(id: string, requiresId: string): Promise<ConceptResult> {
  return call(concept(id, `/prerequisites/${encodeURIComponent(requiresId)}`), "DELETE");
}

export async function publishConcept(id: string): Promise<ConceptResult> {
  return call(concept(id, "/publish"), "POST");
}
