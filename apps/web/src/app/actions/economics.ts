"use server";

// P16.S2.T4 (ECONOMICS-01): finance enters unit rates with their source for the cohort economics report. The API
// enforces the permission, MFA, one currency and audit; earlier rates are kept. This action only forwards.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem, RateIn } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type RateResult = { ok: boolean; error?: string };

export async function setRate(rate: RateIn): Promise<RateResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/economics");
  const res = await api<unknown>("/v1/admin/analytics/economics/rates", { method: "POST", token: t, body: JSON.stringify(rate) });
  revalidatePath("/admin/economics");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const details = Array.isArray(p?.errors) ? p.errors.map((e) => e.msg ?? "").join(" ") : "";
  return { ok: false, error: [p?.detail ?? `That didn't work (${res.status}).`, details].filter(Boolean).join(" ") };
}
