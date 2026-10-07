"use server";

// Help requests, academic reports and written rechecks through the BFF. The API validates ownership, routes academic
// reports to scoped reviewers and keeps staff notes internal.
import { redirect } from "next/navigation";
import type { Problem, RecheckState, StaffSupportTicket, SupportTicket } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(next: string): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect(`/signin?next=${encodeURIComponent(next)}`);
  return t;
}

const detail = (p: unknown, fallback: string) => (p as Problem | null)?.detail ?? fallback;

export type TicketFormState = { error?: string } | undefined;

export async function createTicket(_prev: TicketFormState, form: FormData): Promise<TicketFormState> {
  const t = await token("/help");
  const kind = String(form.get("ref_kind") ?? "");
  const id = String(form.get("ref_id") ?? "");
  const position = form.get("ref_position") ? Number(form.get("ref_position")) : undefined;
  const res = await api<SupportTicket>("/v1/support/tickets", {
    method: "POST",
    token: t,
    body: JSON.stringify({
      category: String(form.get("category") ?? "other"),
      subject: String(form.get("subject") ?? "").trim(),
      body: String(form.get("body") ?? "").trim(),
      reference: kind && id ? { kind, id, ...(position ? { position } : {}) } : undefined,
    }),
  });
  if (!res.ok) {
    const errs = (res.problem as (Problem & { errors?: { msg: string }[] }) | null)?.errors;
    return { error: errs?.length ? `${detail(res.problem, "Please check the form.")} ${errs.map((e) => e.msg).join(" ")}` : detail(res.problem, "Couldn't send your request.") };
  }
  redirect(`/help/${res.data.id}`);
}

export async function replyTicket(id: string, body: string): Promise<{ ok: boolean; error?: string }> {
  const t = await token(`/help/${id}`);
  const res = await api<SupportTicket>(`/v1/support/tickets/${encodeURIComponent(id)}/messages`, { method: "POST", token: t, body: JSON.stringify({ body }) });
  return res.ok ? { ok: true } : { ok: false, error: detail(res.problem, "Couldn't send your reply.") };
}

export async function staffReply(id: string, body: string, internal: boolean, status: string | null): Promise<{ ok: boolean; error?: string }> {
  const t = await token(`/studio/support/${id}`);
  const res = await api<StaffSupportTicket>(`/v1/staff/support/tickets/${encodeURIComponent(id)}/messages`, {
    method: "POST",
    token: t,
    body: JSON.stringify({ body, internal, status: status || null }),
  });
  return res.ok ? { ok: true } : { ok: false, error: detail(res.problem, "Couldn't send the reply.") };
}

export async function requestRecheck(attemptId: string, positions: number[], reason: string): Promise<{ ok: boolean; error?: string }> {
  const t = await token(`/practice/written/${attemptId}`);
  const res = await api<RecheckState>(`/v1/written-attempts/${encodeURIComponent(attemptId)}/recheck`, {
    method: "POST",
    token: t,
    body: JSON.stringify({ positions, reason }),
  });
  return res.ok ? { ok: true } : { ok: false, error: detail(res.problem, "Couldn't request a recheck.") };
}
