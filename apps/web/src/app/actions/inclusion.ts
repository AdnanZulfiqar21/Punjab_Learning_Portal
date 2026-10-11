"use server";

// P05.S2 (INCLUSION-01): inclusion records per mapping and year. The API enforces scope, the source-version rule and
// the independent-reviewer rule; these actions only forward.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type InclusionResult = { ok: true } | { ok: false; error: string };

async function call(path: string, method: "POST" | "PUT", body?: unknown): Promise<InclusionResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/inclusion");
  const res = await api<unknown>(path, { method, token: t, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  revalidatePath("/studio/inclusion");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const extra = Array.isArray(p?.errors) ? ` ${p.errors.map((e) => e.msg ?? "").join(" ")}` : "";
  return { ok: false, error: `${p?.detail ?? `The request failed (${res.status}).`}${extra}` };
}

export async function draftRecord(form: FormData): Promise<InclusionResult> {
  const scope = String(form.get("scope") ?? "");
  const year = String(form.get("year") ?? "");
  return call("/v1/studio/inclusion", "POST", {
    concept_id: String(form.get("concept_id") ?? ""),
    scope,
    year: scope === "full_curriculum" || !year ? null : Number(year),
    state: String(form.get("state") ?? ""),
    reason: String(form.get("reason") ?? "").trim(),
    source: String(form.get("source") ?? "").trim(),
    source_version: String(form.get("source_version") ?? "").trim(),
  });
}

export async function publishRecord(id: string): Promise<InclusionResult> {
  return call(`/v1/studio/inclusion/${encodeURIComponent(id)}/publish`, "POST");
}
