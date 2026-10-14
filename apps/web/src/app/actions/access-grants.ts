"use server";

// P04.S2.T3 (ACCESS-GRANTS-01): finance and the owner grant and revoke scholarship, promotional and pilot access. The
// API enforces the permission, MFA, the exact-email match and the audit; these actions only forward.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { AccessGrantIn, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type GrantResult = { ok: boolean; error?: string };

async function call(path: string, body: unknown): Promise<GrantResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/access");
  const res = await api<unknown>(path, { method: "POST", token: t, body: JSON.stringify(body) });
  revalidatePath("/admin/access");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const details = Array.isArray(p?.errors) ? p.errors.map((e) => e.msg ?? "").join(" ") : "";
  return { ok: false, error: [p?.detail ?? `That didn't work (${res.status}).`, details].filter(Boolean).join(" ") };
}

export async function grantAccess(body: AccessGrantIn): Promise<GrantResult> {
  return call("/v1/admin/entitlements", body);
}

export async function revokeAccess(id: string, reason: string): Promise<GrantResult> {
  return call(`/v1/admin/entitlements/${encodeURIComponent(id)}/revoke`, { reason });
}
