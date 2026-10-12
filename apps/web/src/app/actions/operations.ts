"use server";

// P16.S3.T1 (ROLLOUT-01): an operator changes the share of learners who get a feature. The API enforces the operator
// role, the multi-factor sign-in, the 0-100 range and the written reason, and audits the change; this only forwards.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type RolloutResult = { ok: true } | { ok: false; error: string };

export async function setRollout(key: string, form: FormData): Promise<RolloutResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/service");
  const res = await api<unknown>(`/v1/ops/rollouts/${encodeURIComponent(key)}`, {
    method: "PUT",
    token: t,
    body: JSON.stringify({ percent: Number(form.get("percent")), reason: String(form.get("reason") ?? "").trim() }),
  });
  revalidatePath("/admin/service");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const extra = Array.isArray(p?.errors) ? ` ${p.errors.map((e) => e.msg ?? "").join(" ")}` : "";
  return { ok: false, error: `${p?.detail ?? `The change failed (${res.status}).`}${extra}` };
}
