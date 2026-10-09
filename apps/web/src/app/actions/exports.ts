"use server";

// P16.S4.T2 (EXPORTS-01): background exports through the BFF. The API checks ownership and permission every time.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

const PAGE = "/account/exports";

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(PAGE)}`);
  return t;
}

export type ExportState = { ok?: boolean; error?: string } | undefined;

export async function requestExport(_prev: ExportState, form: FormData): Promise<ExportState> {
  const t = await token();
  const kind = String(form.get("kind") ?? "");
  const params: Record<string, string> = {};
  for (const k of ["since", "until", "action"]) {
    const v = String(form.get(k) ?? "").trim();
    if (v) params[k] = k === "action" ? v : new Date(v).toISOString();
  }
  const res = await api<unknown>("/v1/exports", { method: "POST", token: t, body: JSON.stringify({ kind, params }) });
  revalidatePath(PAGE);
  if (!res.ok) return { error: (res.problem as Problem | null)?.detail ?? "Your export couldn't be requested." };
  return { ok: true };
}

export async function cancelExport(id: string): Promise<void> {
  const t = await token();
  await api<unknown>(`/v1/exports/${encodeURIComponent(id)}/cancel`, { method: "POST", token: t });
  revalidatePath(PAGE);
}

export async function retryExport(id: string): Promise<void> {
  const t = await token();
  await api<unknown>(`/v1/exports/${encodeURIComponent(id)}/retry`, { method: "POST", token: t });
  revalidatePath(PAGE);
}
