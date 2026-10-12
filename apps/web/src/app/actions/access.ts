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

/** P04.S1.T3: take a device off the trial (frees a place; the device can't rejoin by itself). Audited by the API. */
export async function removeTrialDevice(form: FormData): Promise<void> {
  const token = await sessionToken();
  if (!token) redirect("/signin?next=/account");
  const id = String(form.get("device_id") ?? "");
  if (/^[0-9a-f-]{36}$/i.test(id)) await api(`/v1/me/trial/devices/${id}`, { method: "DELETE", token });
  redirect("/account");
}
