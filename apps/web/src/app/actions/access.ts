"use server";

import { redirect } from "next/navigation";
import type { Access, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

/** Start the one-time 30-day free trial. Idempotent: a repeat returns the original dates. */
export async function startTrial(): Promise<{ ok: true; access: Access } | { ok: false; error: string }> {
  const token = await sessionToken();
  if (!token) redirect("/signin?next=/account");
  const res = await api<Access>("/v1/me/trial", { method: "POST", token, headers: { "X-Portal-Client": "web" } });
  if (res.ok) return { ok: true, access: res.data };
  return { ok: false, error: (res.problem as Problem | null)?.detail ?? "The trial couldn't be started." };
}
