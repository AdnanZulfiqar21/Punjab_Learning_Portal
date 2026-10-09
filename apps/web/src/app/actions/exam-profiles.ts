"use server";

// P05.S3: exam profiles. Drafts are entered as data, verified by two different people (never the author) and then
// published with MFA. The API enforces every rule; these actions forward the session and report problems.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

type Out = { ok: boolean; error?: string };

async function call(path: string, method: "POST" | "PUT", body?: unknown): Promise<Out> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/exam-profiles");
  const res = await api<unknown>(path, { method, token: t, body: body === undefined ? undefined : JSON.stringify(body) });
  if (res.ok) {
    revalidatePath("/admin/exam-profiles");
    return { ok: true };
  }
  const p = res.problem as (Problem & { errors?: (string | { msg: string })[] }) | null;
  const details = p?.errors?.map((e) => (typeof e === "string" ? e : e.msg)).join(" ");
  return { ok: false, error: [p?.detail ?? "That didn't work.", details].filter(Boolean).join(" ") };
}

export async function createProfile(code: string, name: string, eligibilityNote: string): Promise<Out> {
  return call("/v1/admin/exam-profiles", "POST", { code, name, eligibility_note: eligibilityNote });
}

export async function saveDraft(profileId: string, versionId: string | null, year: number, rulesJson: string): Promise<Out> {
  let rules: unknown;
  try {
    rules = JSON.parse(rulesJson);
  } catch {
    return { ok: false, error: "The rules must be valid JSON." };
  }
  const path = versionId ? `/v1/admin/exam-profiles/${profileId}/versions/${versionId}` : `/v1/admin/exam-profiles/${profileId}/versions`;
  return call(path, versionId ? "PUT" : "POST", { year, rules });
}

export async function verifyVersion(versionId: string, note: string): Promise<Out> {
  return call(`/v1/admin/exam-profile-versions/${versionId}/verify`, "POST", { note });
}

export async function publishVersion(versionId: string): Promise<Out> {
  return call(`/v1/admin/exam-profile-versions/${versionId}/publish`, "POST");
}

export async function scheduleSession(body: Record<string, string>): Promise<Out> {
  return call("/v1/admin/mock-sessions", "POST", body);
}

export async function accommodate(sessionId: string, email: string, extraMinutes: number, reason: string): Promise<Out> {
  return call(`/v1/admin/mock-sessions/${sessionId}/accommodations`, "POST", { email, extra_minutes: extraMinutes, reason });
}
