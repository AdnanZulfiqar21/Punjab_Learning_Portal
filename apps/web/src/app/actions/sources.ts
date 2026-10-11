"use server";

// SOURCE-INTAKE-01: the owner decides publication rights for a source (the API requires the owner with MFA and
// evidence, and audits it).
import { revalidatePath } from "next/cache";
import { api, sessionToken } from "@/lib/session";

export async function setPublicationRights(id: string, rights: "CONFIRMED" | "DENIED", evidence: string): Promise<{ ok: boolean; error?: string }> {
  const t = await sessionToken();
  if (!t) return { ok: false, error: "Sign in again." };
  const res = await api<unknown>(`/v1/studio/sources/${encodeURIComponent(id)}/publication-rights`, {
    method: "PUT",
    token: t,
    body: JSON.stringify({ rights, evidence }),
  });
  revalidatePath("/studio/sources");
  return res.ok ? { ok: true } : { ok: false, error: res.problem?.detail ?? `The request failed (${res.status}).` };
}
