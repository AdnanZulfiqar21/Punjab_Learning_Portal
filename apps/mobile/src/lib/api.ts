// Mobile API client. The API origin is variant configuration (app.config.ts → extra.apiOrigin); grading, entitlements
// and authorisation stay on the server (roadmap §5.3) — this client only reads published catalogue data.
import Constants from "expo-constants";
import type { Book, Catalogue, Chapter, Problem, SearchResult } from "@portal/contracts";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly kind: "offline" | "not_found" | "server",
    readonly correlationId?: string | null,
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

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const cid = correlationId();
  let res: Response;
  try {
    res = await fetch(`${origin()}${path}`, {
      headers: { Accept: "application/json", "X-Correlation-ID": cid },
      signal: signal ?? AbortSignal.timeout(10_000),
    });
  } catch (e) {
    if ((e as Error).name === "AbortError" && signal?.aborted) throw e;
    throw new ApiError("Can't reach the learning service. Check your connection and try again.", "offline", cid);
  }
  if (res.status === 404) {
    const problem = (await res.json().catch(() => null)) as Problem | null;
    throw new ApiError(problem?.detail ?? "Not found.", "not_found", problem?.correlation_id ?? cid);
  }
  if (!res.ok) {
    const problem = (await res.json().catch(() => null)) as Problem | null;
    throw new ApiError(problem?.detail ?? `Service error (${res.status}).`, "server", problem?.correlation_id ?? cid);
  }
  return (await res.json()) as T;
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
};

export const GRADE_LABEL: Record<number, string> = { 11: "Class XI", 12: "Class XII" };

export function pageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) return "unknown";
  if (start === end) return `${start}`;
  return `${start ?? "?"}–${end ?? "?"}`;
}
