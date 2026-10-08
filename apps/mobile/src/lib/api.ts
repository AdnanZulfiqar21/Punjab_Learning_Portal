// Mobile API client. The API origin is variant configuration (app.config.ts → extra.apiOrigin); grading, entitlements
// and authorisation stay on the server (roadmap §5.3). Authenticated calls send the app session token as a bearer.
import Constants from "expo-constants";
import { Platform } from "react-native";
import type {
  Access,
  AppSession,
  AttemptResult,
  Book,
  Catalogue,
  Chapter,
  Lesson,
  Me,
  PracticeAttempt,
  PracticeAvailability,
  PracticeForm,
  Problem,
  ProfileInput,
  RevealResult,
  RuntimeConfig,
  SaveResult,
  SearchResult,
  SessionCreated,
  SubmitResult,
  TrialDecision,
} from "@portal/contracts";

import { installToken } from "@/lib/install-token";

function deviceName(): string {
  return Platform.OS === "ios" ? "iPhone or iPad" : Platform.OS === "android" ? "Android device" : "Web browser";
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: "offline" | "not_found" | "server" | "unauthorized" | "invalid" | "conflict",
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

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
  headers?: Record<string, string>;
};

// Every request says which client it is and carries this installation's opaque token, so the server can apply the
// trial device rules (roadmap §16.4). Until request attestation exists (B07) these are asserted by the app.
export const CLIENT = Platform.OS === "web" ? "web" : "native";
export const SURFACE: "web" | "ios" | "android" = Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : "web";

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const cid = correlationId();
  const install = await installToken();
  let res: Response;
  try {
    res = await fetch(`${origin()}${path}`, {
      method: opts.method ?? "GET",
      headers: {
        Accept: "application/json",
        "X-Correlation-ID": cid,
        "X-Portal-Client": CLIENT,
        "X-Portal-Install": install,
        ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
        ...opts.headers,
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
  if (res.status === 409) throw new ApiError(detail ?? "This changed elsewhere.", "conflict", ref, problem);
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
  /** Published, live lessons only (independently reviewed); drafts never reach the app. */
  // Premium bodies come back only with a session that has an active plan or trial (review R07).
  lessons: (chapterId: string, token: string | null, signal?: AbortSignal) =>
    request<Lesson[]>(`/v1/chapters/${encodeURIComponent(chapterId)}/lessons`, { token, signal }),

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

  // Plans (P14): trial status, entitlements and the written allowance; the trial is one-time and idempotent.
  access: (token: string, signal?: AbortSignal) => request<Access>("/v1/me/access", { token, signal }),
  // Trial activation is a durable, idempotent claim (roadmap §16.4): retries with the same key recover the same claim.
  claimTrial: async (token: string) =>
    request<TrialDecision>("/v1/me/trial/claims", {
      method: "POST",
      token,
      body: { surface: SURFACE, idempotency_key: `trial-${(await installToken()).slice(0, 40)}`, proof: {}, label: deviceName() },
    }),
  authorizeDevice: (token: string) =>
    request<TrialDecision>("/v1/me/trial/devices", { method: "POST", token, body: { surface: SURFACE, proof: {}, label: deviceName() } }),

  // Practice (P09/P10). Attempt payloads never contain keys; results release them after submission.
  practiceAvailability: (token: string, grade: number, subject: string, signal?: AbortSignal) =>
    request<PracticeAvailability>(`/v1/practice/availability?grade=${grade}&subject=${encodeURIComponent(subject)}`, {
      token,
      signal,
    }),
  createPracticeForm: (token: string, idempotencyKey: string, body: Record<string, unknown>) =>
    request<PracticeForm>("/v1/practice/forms", { method: "POST", token, body, headers: { "Idempotency-Key": idempotencyKey } }),
  startAttempt: (token: string, formId: string) =>
    request<PracticeAttempt>(`/v1/practice/forms/${encodeURIComponent(formId)}/attempt`, { method: "POST", token }),
  attempt: (token: string, id: string, signal?: AbortSignal) =>
    request<PracticeAttempt>(`/v1/attempts/${encodeURIComponent(id)}`, { token, signal }),
  saveAnswers: (token: string, id: string, ops: unknown[]) =>
    request<SaveResult>(`/v1/attempts/${encodeURIComponent(id)}/answers`, { method: "POST", token, body: { ops } }),
  submitAttempt: (token: string, id: string, idempotencyKey: string, ops: unknown[]) =>
    request<SubmitResult>(`/v1/attempts/${encodeURIComponent(id)}/submit`, {
      method: "POST",
      token,
      body: { idempotency_key: idempotencyKey, ops },
    }),
  reveal: (token: string, id: string, position: number) =>
    request<RevealResult>(`/v1/attempts/${encodeURIComponent(id)}/items/${position}/reveal`, { method: "POST", token }),
  result: (token: string, id: string, signal?: AbortSignal) =>
    request<AttemptResult>(`/v1/attempts/${encodeURIComponent(id)}/result`, { token, signal }),
};

export const GRADE_LABEL: Record<number, string> = { 11: "Class XI", 12: "Class XII" };

export function pageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) return "unknown";
  if (start === end) return `${start}`;
  return `${start ?? "?"}–${end ?? "?"}`;
}
