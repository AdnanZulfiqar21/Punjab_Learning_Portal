"use server";

// Server Actions run only via POST and Next.js rejects them when Origin and Host differ (built-in CSRF protection,
// see node_modules/next/dist/docs/01-app/02-guides/data-security.md); the session cookie is also SameSite=Lax.
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import type { ProfileInput, SessionCreated, StudySettings } from "@portal/contracts";
import { DISPLAY_COOKIE, DISPLAY_MAX_AGE_S, fromAccount, parseDisplay, serializeDisplay } from "@/lib/display";
import { api, cookieOptions, PENDING_COOKIE, pendingEmail, SESSION_COOKIE, sessionToken } from "@/lib/session";

export type FormState =
  | {
      error?: string;
      notice?: string;
      fieldErrors?: Record<string, string>;
      /** What was typed, sent back so a failed submit doesn't empty the form (React resets a form after its action).
       * Passwords are never echoed. */
      values?: Record<string, string>;
    }
  | undefined;

function safeNext(next: FormDataEntryValue | null): string {
  const n = typeof next === "string" ? next : "";
  // Only same-site relative paths; never an open redirect. Browsers drop tabs/newlines inside URLs and read "\" as
  // "/", so "/\t/evil" or "/\evil" would become "//evil": any control character or backslash is refused outright.
  if (/[\u0000-\u001f\u007f\\]/.test(n)) return "/account";
  return /^\/(?!\/)/.test(n) ? n : "/account";
}

const PENDING_MAX_AGE_S = 30 * 60;

async function rememberPending(email: string): Promise<void> {
  (await cookies()).set(PENDING_COOKIE, email, { ...cookieOptions(), maxAge: PENDING_MAX_AGE_S });
}

function verifyPath(next: FormDataEntryValue | null): string {
  return `/signin/verify?next=${encodeURIComponent(safeNext(next))}`;
}

/** Exchange an access token (the portal's password issuer) for an application session cookie, then go on. */
async function startSession(accessToken: string, next: FormDataEntryValue | null): Promise<FormState> {
  const h = await headers();
  const created = await api<SessionCreated>("/v1/sessions", {
    method: "POST",
    token: accessToken,
    body: JSON.stringify({ kind: "web", device_label: "Web browser" }),
    headers: { "User-Agent": h.get("user-agent") ?? "web" },
  });
  if (!created.ok) return { error: "Could not start a session. Please try again." };
  const jar = await cookies();
  jar.set(SESSION_COOKIE, created.data.session_token, cookieOptions());
  jar.delete(PENDING_COOKIE);
  // SETTINGS-01: a device without its own display choice takes the account's usual settings; its own is never replaced.
  if (!parseDisplay(jar.get(DISPLAY_COOKIE)?.value)?.own) {
    const usual = await api<StudySettings>("/v1/me/settings", { token: created.data.session_token });
    if (usual.ok && usual.data.saved) {
      jar.set(DISPLAY_COOKIE, serializeDisplay(fromAccount(usual.data)), { ...cookieOptions(), httpOnly: false, maxAge: DISPLAY_MAX_AGE_S });
    }
  }
  redirect(safeNext(next));
}

const EMAIL_DOWN = "We couldn't send the email just now. Please try again in a minute.";

/** Email + password sign-in. An account whose email isn't confirmed yet is sent a fresh code and taken to enter it. */
export async function signInWithPassword(_prev: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const values = { email };
  if (!email || !password) return { error: "Enter your email and password.", values };
  // Development only: the dev shortcut can simulate an MFA sign-in so MFA-gated staff actions can be exercised locally.
  const mfa = form.get("mfa") === "on";
  const tok = await api<{ access_token: string }>(mfa ? "/v1/dev-auth/token" : "/v1/auth/token", {
    method: "POST",
    body: JSON.stringify(mfa ? { email, password, mfa } : { email, password }),
  });
  if (!tok.ok) {
    if (tok.status === 403 && tok.problem?.title === "EMAIL_NOT_VERIFIED") {
      await rememberPending(email);
      await api("/v1/auth/resend-code", { method: "POST", body: JSON.stringify({ email }) }); // a recent code may stand
      redirect(verifyPath(form.get("next")));
    }
    return { error: tok.status === 401 ? "Email or password is incorrect." : "Sign-in is unavailable right now.", values };
  }
  return startSession(tok.data.access_token, form.get("next"));
}

const REGISTER_FIELD_ERRORS: Record<string, string> = {
  email: "Enter a valid email address.",
  password: "Use at least 10 characters.",
  phone: "Enter a mobile number like 0300 1234567 (or +country code for other countries).",
  date_of_birth: "Enter your real date of birth.",
};

/** Create an account: the API emails a 6-digit code (Resend), and the next page asks for it. Mobile number and date of
 * birth are required (owner 2026-11-11, not verified); promotional emails only with the unticked opt-in. */
export async function registerWithPassword(_prev: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const phone = String(form.get("phone") ?? "").trim();
  const dateOfBirth = String(form.get("date_of_birth") ?? "");
  const marketing = form.get("marketing_emails") === "on";
  const values = { email, phone, date_of_birth: dateOfBirth, marketing_emails: marketing ? "on" : "" };
  const missing: Record<string, string> = {};
  if (password.length < 10) missing.password = REGISTER_FIELD_ERRORS.password;
  if (!phone) missing.phone = "Enter your mobile number.";
  if (!dateOfBirth) missing.date_of_birth = "Enter your date of birth.";
  if (Object.keys(missing).length) return { fieldErrors: missing, values };
  const res = await api("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      phone,
      date_of_birth: dateOfBirth,
      marketing_emails: marketing,
    }),
  });
  if (!res.ok) {
    if (res.status === 422) {
      const fields = (res.problem?.errors ?? []).map((e) => String(e.loc.at(-1))).filter((f) => f in REGISTER_FIELD_ERRORS);
      const fieldErrors = Object.fromEntries((fields.length ? fields : ["email"]).map((f) => [f, REGISTER_FIELD_ERRORS[f]]));
      return { fieldErrors, values };
    }
    return { error: res.status === 503 ? EMAIL_DOWN : "Registration is unavailable right now.", values };
  }
  await rememberPending(email);
  redirect(verifyPath(form.get("next")));
}

/** Confirm the email with its code; this also signs the person in. */
export async function verifyEmailCode(_prev: FormState, form: FormData): Promise<FormState> {
  const email = await pendingEmail();
  if (!email) redirect("/signin");
  const code = String(form.get("code") ?? "").replace(/\s/g, "");
  if (!/^\d{6}$/.test(code)) return { fieldErrors: { code: "Enter the 6 digits from the email." } };
  const res = await api<{ access_token: string }>("/v1/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) {
    if (res.status === 400) return { fieldErrors: { code: "That code is wrong or has expired. Check the email or ask for a new code." } };
    return { error: "We couldn't check the code right now. Please try again." };
  }
  return startSession(res.data.access_token, form.get("next"));
}

/** Send a new code to the email waiting for one. */
export async function resendEmailCode(): Promise<FormState> {
  const email = await pendingEmail();
  if (!email) redirect("/signin");
  const res = await api("/v1/auth/resend-code", { method: "POST", body: JSON.stringify({ email }) });
  if (res.ok) return { notice: "A new code is on its way. Check your inbox (and the spam folder)." };
  if (res.status === 429) {
    const wait = Number((res.problem as { retry_after?: number } | null)?.retry_after ?? 60);
    return { error: `Please wait ${wait} seconds before asking for another code.` };
  }
  return { error: res.status === 503 ? EMAIL_DOWN : "We couldn't send a new code right now." };
}

export async function revokeSession(form: FormData): Promise<void> {
  const token = await sessionToken();
  const id = String(form.get("session_id") ?? "");
  if (token && /^[0-9a-f-]{36}$/i.test(id)) await api(`/v1/me/sessions/${id}`, { method: "DELETE", token });
  redirect("/account");
}

export async function revokeOtherSessions(): Promise<void> {
  const token = await sessionToken();
  if (token) await api("/v1/me/sessions/revoke-others", { method: "POST", token });
  redirect("/account");
}

const LIST_FIELDS = ["subjects", "target_exams"] as const;

export async function saveProfile(_prev: FormState, form: FormData): Promise<FormState> {
  const token = await sessionToken();
  if (!token) redirect("/signin?next=/onboarding");
  const num = (k: string) => (form.get(k) ? Number(form.get(k)) : null);
  const body: ProfileInput = {
    grade: (num("grade") as 11 | 12 | null) ?? null,
    stream: (form.get("stream") as ProfileInput["stream"]) || null,
    subjects: form.getAll(LIST_FIELDS[0]) as ProfileInput["subjects"],
    target_exams: form.getAll(LIST_FIELDS[1]) as ProfileInput["target_exams"],
    target_year: num("target_year"),
    explanation_language: (form.get("explanation_language") as ProfileInput["explanation_language"]) || "en",
    daily_minutes: num("daily_minutes"),
  };
  const res = await api("/v1/me/profile", { method: "PUT", token, body: JSON.stringify(body) });
  if (!res.ok) {
    if (res.status === 401) redirect("/signin?next=/onboarding");
    const errs = (res.problem?.errors ?? []).map((e) => `${e.loc.at(-1)}: ${e.msg}`);
    return { error: errs.length ? `Please check: ${errs.join("; ")}` : "Could not save your preferences." };
  }
  redirect("/learn");
}
