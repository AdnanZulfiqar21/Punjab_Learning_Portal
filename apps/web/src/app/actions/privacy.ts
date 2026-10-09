"use server";

import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export async function requestDeletion(confirmEmail: string, reason: string): Promise<{ ok: boolean; message: string }> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/account");
  const res = await api<{ ticket_id: string }>("/v1/me/deletion-request", {
    method: "POST",
    token: t,
    body: JSON.stringify({ confirm_email: confirmEmail, reason: reason || null }),
  });
  if (res.ok) return { ok: true, message: "We've received your request. Our support team will contact you through your help requests." };
  return { ok: false, message: (res.problem as Problem | null)?.detail ?? "We couldn't record your request." };
}
