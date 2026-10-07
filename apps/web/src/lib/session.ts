// Server-only session helpers (P04.S1.T2). The application session token lives in an HTTP-only cookie; browser
// JavaScript never sees it. The web server forwards it to the API as a bearer token, server to server.
import { cookies } from "next/headers";
import { connection } from "next/server";
import type { AppSession, Me, Problem, RuntimeConfig } from "@portal/contracts";
import { readRuntimeConfig } from "@/lib/runtime-config";

export const SESSION_COOKIE = "portal_session";
const SESSION_MAX_AGE_S = 30 * 24 * 60 * 60; // matches the API's absolute web-session lifetime

export function cookieOptions() {
  const { role } = readRuntimeConfig();
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: role === "staging" || role === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  };
}

export async function sessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; status: number; problem: Problem | null };

/** Call the API on behalf of the signed-in learner (or anonymously when `token` is absent). */
export async function api<T>(path: string, init: RequestInit & { token?: string } = {}): Promise<ApiResult<T>> {
  await connection();
  const { token, headers, ...rest } = init;
  const res = await fetch(`${readRuntimeConfig().apiOrigin}${path}`, {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(rest.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      "X-Correlation-ID": crypto.randomUUID().replaceAll("-", ""),
      ...headers,
    },
    cache: "no-store",
    signal: AbortSignal.timeout(8000),
  });
  if (res.status === 204) return { ok: true, data: undefined as T };
  const body = await res.json().catch(() => null);
  return res.ok ? { ok: true, data: body as T } : { ok: false, status: res.status, problem: body as Problem | null };
}

/** The signed-in learner, or null when there is no valid session (expired, revoked or absent). */
export async function currentUser(): Promise<{ me: Me; token: string } | null> {
  const token = await sessionToken();
  if (!token) return null;
  const res = await api<Me>("/v1/me", { token });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) return null;
    throw new Error(res.problem?.detail ?? `Service error (${res.status}).`);
  }
  return { me: res.data, token };
}

export async function listSessions(token: string): Promise<AppSession[]> {
  const res = await api<AppSession[]>("/v1/me/sessions", { token });
  if (!res.ok) throw new Error(res.problem?.detail ?? "Could not load sessions.");
  return res.data;
}

export async function signInMethods(): Promise<string[]> {
  const res = await api<RuntimeConfig>("/v1/runtime-config");
  return res.ok ? res.data.sign_in_methods : [];
}
