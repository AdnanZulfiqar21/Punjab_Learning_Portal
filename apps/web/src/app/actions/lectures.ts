"use server";

// Lecture production records (P07.S4.T3, LECTURE-01): voices, lectures, master, captions, transcript and review.
// The API enforces scope, the owner-only voice approval (MFA) and the independent review; these actions only forward.
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type LectureResult = { ok: true; id?: string } | { ok: false; error: string; errors?: string[] };

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/lectures");
  return t;
}

async function call(path: string, method: "POST" | "PUT", body: unknown): Promise<LectureResult> {
  const res = await api<{ id?: string }>(path, { method, token: await token(), body: JSON.stringify(body) });
  if (res.ok) return { ok: true, id: res.data?.id };
  const p = res.problem as (Problem & { errors?: unknown[] }) | null;
  const errors = Array.isArray(p?.errors) ? p.errors.map((e) => (typeof e === "string" ? e : JSON.stringify(e))) : undefined;
  return { ok: false, error: p?.detail ?? `The request failed (${res.status}).`, errors };
}

const lecture = (id: string, part: string) => `/v1/studio/lectures/${encodeURIComponent(id)}/${part}`;

export async function proposeVoice(form: FormData): Promise<LectureResult> {
  return call("/v1/studio/voices", "POST", {
    name: String(form.get("name") ?? ""),
    language: String(form.get("language") ?? "roman_ur"),
    tool: String(form.get("tool") ?? ""),
    voice_ref: String(form.get("voice_ref") ?? ""),
    notes: String(form.get("notes") ?? ""),
  });
}

export async function decideVoice(id: string, action: "approve" | "retire", evidence: string): Promise<LectureResult> {
  return call(`/v1/studio/voices/${encodeURIComponent(id)}/${action}`, "POST", { evidence });
}

export async function startLecture(form: FormData): Promise<LectureResult> {
  return call("/v1/studio/lectures", "POST", {
    storyboard_item_id: String(form.get("storyboard_item_id") ?? ""),
    narration_language: String(form.get("narration_language") ?? "roman_ur"),
    voice_id: String(form.get("voice_id") ?? ""),
  });
}

export async function registerMaster(id: string, form: FormData): Promise<LectureResult> {
  return call(lecture(id, "master"), "PUT", {
    filename: String(form.get("filename") ?? ""),
    sha256: String(form.get("sha256") ?? "").trim().toLowerCase(),
    bytes: Number(form.get("bytes") ?? 0),
    duration_s: Number(form.get("duration_s") ?? 0),
    location: String(form.get("location") ?? ""),
  });
}

export async function attachCaptions(id: string, form: FormData): Promise<LectureResult> {
  return call(lecture(id, "captions"), "PUT", {
    language: String(form.get("language") ?? "roman_ur"),
    asset_version_id: String(form.get("asset_version_id") ?? "").trim(),
  });
}

export async function saveTranscript(id: string, scenes: { scene_id: string; text: string }[]): Promise<LectureResult> {
  return call(lecture(id, "transcript"), "PUT", { scenes });
}

export async function submitLecture(id: string): Promise<LectureResult> {
  return call(lecture(id, "submit"), "POST", {});
}

export async function reviewLecture(id: string, decision: "approve" | "request_changes", checklist: Record<string, boolean>, notes: string): Promise<LectureResult> {
  return call(lecture(id, "review"), "POST", { decision, checklist, notes });
}
