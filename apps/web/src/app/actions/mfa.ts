"use server";

// STAFF-MFA-01: two-step sign-in with an authenticator app. The API holds every rule (the code check, the lock after
// wrong codes, the twelve-hour window, the audit); these actions forward the caller's own session.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { MfaEnrolment, MfaStatus, Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

export type MfaResult<T = undefined> = { ok: true; data: T } | { ok: false; message: string };

const CODE = /^[A-Za-z0-9 -]{6,20}$/;

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/account%23two-step");
  return t;
}

function failed(problem: Problem | null, fallback: string): { ok: false; message: string } {
  return { ok: false, message: problem?.detail ?? fallback };
}

/** Start set-up: the key for the authenticator app (shown once). Needs a recent sign-in. */
export async function startTwoStep(): Promise<MfaResult<MfaEnrolment>> {
  const res = await api<MfaEnrolment>("/v1/me/mfa/enrol", { method: "POST", token: await token() });
  if (!res.ok && res.problem?.title === "REAUTH_REQUIRED") redirect("/signin?next=/account%23two-step&reason=reauth");
  return res.ok ? { ok: true, data: res.data } : failed(res.problem, "We couldn't start the set-up. Please try again.");
}

/** Finish set-up with the first code. Returns the one-time recovery codes (shown once). */
export async function confirmTwoStep(code: string): Promise<MfaResult<string[]>> {
  if (!CODE.test(code)) return { ok: false, message: "Enter the 6-digit code from your authenticator app." };
  const res = await api<{ recovery_codes: string[] }>("/v1/me/mfa/confirm", {
    method: "POST",
    token: await token(),
    body: JSON.stringify({ code }),
  });
  if (!res.ok) return failed(res.problem, "We couldn't check that code. Please try again.");
  revalidatePath("/account");
  return { ok: true, data: res.data.recovery_codes };
}

/** Prove the second factor on this device (lasts twelve hours). */
export async function verifyTwoStep(code: string): Promise<MfaResult<MfaStatus>> {
  if (!CODE.test(code)) return { ok: false, message: "Enter the 6-digit code from your authenticator app." };
  const res = await api<MfaStatus>("/v1/me/mfa/verify", { method: "POST", token: await token(), body: JSON.stringify({ code }) });
  if (!res.ok) return failed(res.problem, "We couldn't check that code. Please try again.");
  revalidatePath("/account");
  return { ok: true, data: res.data };
}

/** Turn two-step sign-in off. Needs a code. */
export async function turnOffTwoStep(code: string): Promise<MfaResult> {
  if (!CODE.test(code)) return { ok: false, message: "Enter the 6-digit code from your authenticator app." };
  const res = await api<undefined>("/v1/me/mfa/disable", { method: "POST", token: await token(), body: JSON.stringify({ code }) });
  if (!res.ok) return failed(res.problem, "We couldn't turn it off. Please try again.");
  revalidatePath("/account");
  return { ok: true, data: undefined };
}
