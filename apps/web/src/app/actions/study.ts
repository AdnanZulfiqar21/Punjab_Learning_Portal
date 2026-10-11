"use server";

// P11.S2.T2 (STUDY-TOOLS-01): private lesson notes, topic favourites and saved formulas. Conflicts come back with the
// current note so the learner chooses; nothing is merged or overwritten silently.
import { revalidatePath } from "next/cache";
import type { StudyNote } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type NoteResult =
  | { ok: true; note: StudyNote }
  | { ok: false; conflict: "NOTE_CHANGED" | "NOTE_DELETED"; current: StudyNote; message: string }
  | { ok: false; conflict?: undefined; message: string };

function noteResult(res: Awaited<ReturnType<typeof api<StudyNote>>>): NoteResult {
  if (res.ok) return { ok: true, note: res.data };
  const p = res.problem as { code_reason?: string; current?: StudyNote; detail?: string } | null;
  if (res.status === 409 && (p?.code_reason === "NOTE_CHANGED" || p?.code_reason === "NOTE_DELETED") && p.current) {
    return { ok: false, conflict: p.code_reason, current: p.current, message: p.detail ?? "This note changed elsewhere." };
  }
  return { ok: false, message: p?.detail ?? "Couldn't save your note. It's kept on this device." };
}

export async function saveNote(lessonId: string, text: string, baseRevision: number): Promise<NoteResult> {
  const t = await sessionToken();
  if (!t) return { ok: false, message: "Sign in again to save your note. It's kept on this device." };
  const res = await api<StudyNote>(`/v1/me/lessons/${encodeURIComponent(lessonId)}/note`, {
    method: "PUT",
    token: t,
    body: JSON.stringify({ text, base_revision: baseRevision }),
  });
  return noteResult(res);
}

export async function deleteNote(lessonId: string, baseRevision: number): Promise<NoteResult> {
  const t = await sessionToken();
  if (!t) return { ok: false, message: "Sign in again to delete your note." };
  const res = await api<StudyNote>(`/v1/me/lessons/${encodeURIComponent(lessonId)}/note?base_revision=${baseRevision}`, {
    method: "DELETE",
    token: t,
  });
  return noteResult(res);
}

export async function setFavourite(topicId: string, on: boolean): Promise<{ ok: boolean; message?: string }> {
  const t = await sessionToken();
  if (!t) return { ok: false, message: "Sign in to keep favourites." };
  const res = await api<null>(`/v1/me/favourites/topics/${encodeURIComponent(topicId)}`, { method: on ? "PUT" : "DELETE", token: t });
  revalidatePath("/study");
  return res.ok ? { ok: true } : { ok: false, message: res.problem?.detail ?? "Couldn't change the favourite." };
}

export async function saveFormula(lessonId: string, blockIndex: number): Promise<{ ok: boolean; message?: string }> {
  const t = await sessionToken();
  if (!t) return { ok: false, message: "Sign in to save formulas." };
  const res = await api<unknown>("/v1/me/formulas", {
    method: "POST",
    token: t,
    body: JSON.stringify({ lesson_id: lessonId, block_index: blockIndex }),
  });
  revalidatePath("/study");
  return res.ok ? { ok: true } : { ok: false, message: res.problem?.detail ?? "Couldn't save the formula." };
}

export async function removeFormula(formulaId: string): Promise<void> {
  const t = await sessionToken();
  if (!t) return;
  await api<null>(`/v1/me/formulas/${encodeURIComponent(formulaId)}`, { method: "DELETE", token: t });
  revalidatePath("/study");
}
