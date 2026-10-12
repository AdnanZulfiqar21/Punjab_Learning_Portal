"use server";

// P16.S4.T3 (OWNER-VALIDATION-01): the owner adds and removes staff roles. The API enforces owner/admin with MFA, the
// exact-email match, no self-changes and the audit; these actions only forward.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem, StaffByEmailIn } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type StaffResult = { ok: boolean; error?: string };

async function call(path: string, body: unknown): Promise<StaffResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/staff");
  const res = await api<unknown>(path, { method: "POST", token: t, body: JSON.stringify(body) });
  revalidatePath("/admin/staff");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const details = Array.isArray(p?.errors) ? p.errors.map((e) => e.msg ?? "").join(" ") : "";
  return { ok: false, error: [p?.detail ?? `That didn't work (${res.status}).`, details].filter(Boolean).join(" ") };
}

export async function addStaff(body: StaffByEmailIn): Promise<StaffResult> {
  return call("/v1/admin/staff", body);
}

export async function removeStaffRole(grantId: string, reason: string): Promise<StaffResult> {
  return call(`/v1/admin/role-grants/${encodeURIComponent(grantId)}/revoke`, { reason });
}
