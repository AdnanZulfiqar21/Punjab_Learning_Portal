"use server";

// P14.S1.T1 (PRODUCTS-01): sellable products. Finance staff define drafts, put them on sale, add price versions and
// retire them; the API enforces the permission, MFA, scope rules, immutability and audit. These actions only forward.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { CommerceTermsIn, Problem, ProductIn } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type ProductResult = { ok: boolean; error?: string };

async function call(path: string, method: "POST" | "PUT", body: unknown): Promise<ProductResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/admin/products");
  const res = await api<unknown>(path, { method, token: t, body: JSON.stringify(body) });
  revalidatePath("/admin/products");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const details = Array.isArray(p?.errors) ? p.errors.map((e) => e.msg ?? "").join(" ") : "";
  return { ok: false, error: [p?.detail ?? `That didn't work (${res.status}).`, details].filter(Boolean).join(" ") };
}

export async function createProduct(body: ProductIn): Promise<ProductResult> {
  return call("/v1/admin/products", "POST", body);
}

export async function moveProduct(id: string, to: "activate" | "retire", reason: string): Promise<ProductResult> {
  return call(`/v1/admin/products/${encodeURIComponent(id)}/${to}`, "POST", { reason });
}

export async function addPrice(
  id: string,
  price: { currency: string; amount_minor: number | null; on_sale: boolean; starts_at: string | null; reason: string },
): Promise<ProductResult> {
  return call(`/v1/admin/products/${encodeURIComponent(id)}/prices`, "POST", { channel: "web", ...price });
}

/** P14.S1.T3 (PRICING-01): write the draft purchase terms (one open draft; only its author changes it). */
export async function saveTerms(terms: CommerceTermsIn): Promise<ProductResult> {
  return call("/v1/admin/commerce-terms/draft", "PUT", terms);
}

/** Publish the draft terms; a different finance person than the drafter must do it (two people). */
export async function publishTerms(reason: string): Promise<ProductResult> {
  return call("/v1/admin/commerce-terms/publish", "POST", { reason });
}
