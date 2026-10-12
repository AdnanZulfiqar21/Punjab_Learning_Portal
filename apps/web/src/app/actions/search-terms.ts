"use server";

// P11.S2.T3 (SEARCH-01): search term groups (English ↔ Urdu ↔ Roman Urdu) from the owner's material. The API enforces
// scope, the script of each form, clashes and the second-person approval; these actions only forward.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type SearchTermResult = { ok: true } | { ok: false; error: string };

async function call(path: string, body?: unknown): Promise<SearchTermResult> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/search-terms");
  const res = await api<unknown>(path, { method: "POST", token: t, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  revalidatePath("/studio/search-terms");
  if (res.ok) return { ok: true };
  const p = res.problem as (Problem & { errors?: { msg?: string }[] }) | null;
  const extra = Array.isArray(p?.errors) ? ` ${p.errors.map((e) => e.msg ?? "").join(" ")}` : "";
  return { ok: false, error: `${p?.detail ?? `The request failed (${res.status}).`}${extra}` };
}

/** One form per line in each box; blank lines are ignored. */
function lines(form: FormData, name: string): string[] {
  return String(form.get(name) ?? "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export async function proposeTerms(form: FormData): Promise<SearchTermResult> {
  const forms = [
    ...lines(form, "en").map((text) => ({ language: "en", text })),
    ...lines(form, "ur").map((text) => ({ language: "ur", text })),
    ...lines(form, "roman_ur").map((text) => ({ language: "roman_ur", text })),
  ];
  if (forms.length < 2) return { ok: false, error: "Give at least two forms of the term." };
  return call("/v1/studio/search-terms", {
    grade: Number(form.get("grade")),
    subject: String(form.get("subject") ?? ""),
    forms,
    source_ref: String(form.get("source_ref") ?? "").trim(),
  });
}

export async function approveTerms(id: string): Promise<SearchTermResult> {
  return call(`/v1/studio/search-terms/${encodeURIComponent(id)}/approve`);
}

export async function retireTerms(id: string, reason: string): Promise<SearchTermResult> {
  return call(`/v1/studio/search-terms/${encodeURIComponent(id)}/retire`, { reason });
}
