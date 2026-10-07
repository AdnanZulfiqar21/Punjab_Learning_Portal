// Mobile API client. The API origin is variant configuration (app.config.ts → extra.apiOrigin); grading, entitlements
// and authorisation stay on the server (roadmap §5.3). Authenticated calls send the app session token as a bearer.
import Constants from "expo-constants";
import type {
  AppSession,
  Book,
  Catalogue,
  Chapter,
  Me,
  Problem,
  ProfileInput,
  RuntimeConfig,
  SearchResult,
  SessionCreated,
} from "@portal/contracts";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: "offline" | "not_found" | "server" | "unauthorized" | "invalid",
    readonly correlationId?: string | null,
    readonly problem?: Problem | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function origin(): string {
  const value = Constants.expoConfig?.extra?.apiOrigin;
  if (typeof value !== "string" || !value) throw new ApiError("App configuration is missing the API address.", "server");
  return value;
}

function correlationId(): string {
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

type RequestOptions = { method?: string; body?: unknown; token?: string | null; signal?: AbortSignal };

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const cid = correlationId();
  let res: Response;
  try {
    res = await fetch(`${origin()}${path}`, {
      method: opts.method ?? "GET",
      headers: {
        Accept: "application/json",
        "X-Correlation-ID": cid,
        ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal ?? AbortSignal.timeout(15_000),
    });
  } catch (e) {
    if ((e as Error).name === "AbortError" && opts.signal?.aborted) throw e;
    throw new ApiError("Can't reach the learning service. Check your connection and try again.", "offline", cid);
  }
  if (res.status === 204) return undefined as T;
  if (res.ok) return (await res.json()) as T;
  const problem = (await res.json().catch(() => null)) as Problem | null;
  const ref = problem?.correlation_id ?? cid;
  const detail = problem?.detail;
  if (res.status === 404 || res.status === 410) throw new ApiError(detail ?? "Not found.", "not_found", ref, problem);
  if (res.status === 401) throw new ApiError(detail ?? "Please sign in again.", "unauthorized", ref, problem);
  if (res.status === 422) throw new ApiError(detail ?? "Please check your entries.", "invalid", ref, problem);
  throw new ApiError(detail ?? `Service error (${res.status}).`, "server", ref, problem);
}

function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal });
}

export const api = {
  catalogue: (signal?: AbortSignal) => getJSON<Catalogue>("/v1/catalogue", signal),
  bookFor: (grade: number, subject: string, signal?: AbortSignal) =>
    getJSON<Book>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/book`, signal),
  chapter: (id: string, signal?: AbortSignal) => getJSON<Chapter>(`/v1/chapters/${encodeURIComponent(id)}`, signal),
  search: (q: string, grade?: number, signal?: AbortSignal) => {
    const params = new URLSearchParams({ q });
    if (grade) params.set("grade", String(grade));
    return getJSON<SearchResult>(`/v1/search?${params.toString()}`, signal);
  },
  runtimeConfig: (signal?: AbortSignal) => getJSON<RuntimeConfig>("/v1/runtime-config", signal),

  // Development identity adapter: the API exposes it only in development/test and keeps it out of the contract.
  devRegister: (email: string, password: string) =>
    request<void>("/v1/dev-auth/register", { method: "POST", body: { email, password } }),
  devToken: (email: string, password: string) =>
    request<{ access_token: string }>("/v1/dev-auth/token", { method: "POST", body: { email, password } }),

  // App sessions (IMPL-12) are created only from a verified IdP access token.
  createSession: (idpToken: string, deviceLabel: string) =>
    request<SessionCreated>("/v1/sessions", {
      method: "POST",
      token: idpToken,
      body: { kind: "native", device_label: deviceLabel },
    }),
  me: (token: string, signal?: AbortSignal) => request<Me>("/v1/me", { token, signal }),
  sessions: (token: string, signal?: AbortSignal) => request<AppSession[]>("/v1/me/sessions", { token, signal }),
  revokeSession: (token: string, id: string) =>
    request<void>(`/v1/me/sessions/${encodeURIComponent(id)}`, { method: "DELETE", token }),
  revokeOthers: (token: string) => request<void>("/v1/me/sessions/revoke-others", { method: "POST", token }),
  signOut: (token: string) => request<void>("/v1/me/session", { method: "DELETE", token }),
  saveProfile: (token: string, body: ProfileInput) => request<unknown>("/v1/me/profile", { method: "PUT", token, body }),
};

export const GRADE_LABEL: Record<number, string> = { 11: "Class XI", 12: "Class XII" };

export function pageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) return "unknown";
  if (start === end) return `${start}`;
  return `${start ?? "?"}–${end ?? "?"}`;
}
