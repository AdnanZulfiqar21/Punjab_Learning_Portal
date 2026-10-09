"use server";

// P06.S2: commit or discard a previewed import. The API re-validates every row and writes all of them or none.
import { redirect } from "next/navigation";
import type { ImportBatch, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export async function commitImport(id: string): Promise<{ ok: true; batch: ImportBatch } | { ok: false; error: string }> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/imports");
  const res = await api<ImportBatch>(`/v1/studio/imports/${encodeURIComponent(id)}/commit`, { method: "POST", token: t });
  return res.ok ? { ok: true, batch: res.data } : { ok: false, error: (res.problem as Problem | null)?.detail ?? "Couldn't commit the import." };
}

export async function discardImport(id: string): Promise<{ ok: boolean; error?: string }> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/imports");
  const res = await api<ImportBatch>(`/v1/studio/imports/${encodeURIComponent(id)}/discard`, { method: "POST", token: t });
  return res.ok ? { ok: true } : { ok: false, error: (res.problem as Problem | null)?.detail ?? "Couldn't discard the import." };
}
