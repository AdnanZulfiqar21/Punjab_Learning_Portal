"use server";

// P06.S1.T1 (CATALOGUE-ADMIN-01): preview and apply catalogue changes through the BFF (owner/admin, MFA).
import { redirect } from "next/navigation";
import type { CatalogueApplied, CataloguePreview, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/catalogue");
  return t;
}

export type PreviewState = { preview?: CataloguePreview; error?: string } | undefined;
export type ApplyState = { applied?: CatalogueApplied; error?: string; code?: string } | undefined;

export async function previewCatalogue(): Promise<PreviewState> {
  const res = await api<CataloguePreview>("/v1/admin/catalogue/preview", { method: "POST", token: await token() });
  if (!res.ok) return { error: (res.problem as Problem | null)?.detail ?? "The preview couldn't be prepared." };
  return { preview: res.data };
}

export async function applyCatalogue(_prev: ApplyState, form: FormData): Promise<ApplyState> {
  const body = { input_sha256: String(form.get("input_sha256") ?? ""), acknowledge_dependencies: form.get("acknowledge") === "on" };
  const res = await api<CatalogueApplied>("/v1/admin/catalogue/apply", { method: "POST", token: await token(), body: JSON.stringify(body) });
  if (!res.ok) {
    const p = res.problem as (Problem & { code_reason?: string }) | null;
    return { error: p?.detail ?? "The catalogue couldn't be applied.", code: p?.code_reason };
  }
  return { applied: res.data };
}
