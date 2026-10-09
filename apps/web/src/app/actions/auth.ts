"use server";

// Server Actions run only via POST and Next.js rejects them when Origin and Host differ (built-in CSRF protection,
// see node_modules/next/dist/docs/01-app/02-guides/data-security.md); the session cookie is also SameSite=Lax.
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import type { ProfileInput, SessionCreated } from "@portal/contracts";
import { api, cookieOptions, SESSION_COOKIE, sessionToken } from "@/lib/session";

export type FormState = { error?: string; fieldErrors?: Record<string, string> } | undefined;

function safeNext(next: FormDataEntryValue | null): string {
  const n = typeof next === "string" ? next : "";
  // Only same-site relative paths; never an open redirect. Browsers drop tabs/newlines inside URLs and read "\" as
  // "/", so "/\t/evil" or "/\evil" would become "//evil": any control character or backslash is refused outright.
  if (/[\u0000-\u001f\u007f\\]/.test(n)) return "/account";
  return /^\/(?!\/)/.test(n) ? n : "/account";
}

/** Development-only email/password sign-in (the API refuses this adapter outside development/test). */
export async function signInWithPassword(_prev: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!email || !password) return { error: "Enter your email and password." };
  // Development adapter only: lets staff simulate an MFA sign-in so MFA-gated actions can be exercised locally.
  const mfa = form.get("mfa") === "on";
  const tok = await api<{ access_token: string }>("/v1/dev-auth/token", {
    method: "POST",
    body: JSON.stringify({ email, password, mfa }),
  });
  if (!tok.ok) {
    return { error: tok.status === 401 ? "Email or password is incorrect." : "Sign-in is unavailable right now." };
  }
  const h = await headers();
  const created = await api<SessionCreated>("/v1/sessions", {
    method: "POST",
    token: tok.data.access_token,
    body: JSON.stringify({ kind: "web", device_label: "Web browser" }),
    headers: { "User-Agent": h.get("user-agent") ?? "web" },
  });
  if (!created.ok) return { error: "Could not start a session. Please try again." };
  (await cookies()).set(SESSION_COOKIE, created.data.session_token, cookieOptions());
  redirect(safeNext(form.get("next")));
}

/** Development-only registration (enumeration-safe on the API side). */
export async function registerWithPassword(_prev: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (password.length < 10) return { fieldErrors: { password: "Use at least 10 characters." } };
  const res = await api("/v1/dev-auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
  if (!res.ok) {
    return res.status === 422 ? { fieldErrors: { email: "Enter a valid email address." } } : { error: "Registration is unavailable." };
  }
  return signInWithPassword(undefined, form);
}

export async function signOut(): Promise<void> {
  const token = await sessionToken();
  if (token) await api("/v1/me/session", { method: "DELETE", token }).catch(() => undefined);
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/");
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
