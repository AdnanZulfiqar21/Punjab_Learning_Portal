// Server-side API client. The API origin is read from the runtime environment on every request, never baked into
// the build (roadmap §5.5: one immutable artifact promoted between environments).
import { connection } from "next/server";
import { cache } from "react";
import type { Book, Catalogue, Chapter, Problem, SearchResult } from "@portal/contracts";

export class ApiUnavailableError extends Error {
  constructor(
    message: string,
    readonly correlationId?: string | null,
  ) {
    super(message);
    this.name = "ApiUnavailableError";
  }
}

export type Result<T> = { ok: true; data: T } | { ok: false; status: 404; problem: Problem };

const DEPLOYED_ROLES = new Set(["staging", "production"]);

function apiOrigin(): string {
  const origin = process.env.PORTAL_API_INTERNAL_ORIGIN;
  if (origin) return origin;
  // A deployed server must be told where the API is; it never falls back to a development default.
  if (DEPLOYED_ROLES.has(process.env.PORTAL_ROLE ?? "")) {
    throw new Error("PORTAL_API_INTERNAL_ORIGIN must be set for staging/production web servers");
  }
  return "http://127.0.0.1:8100";
}

async function getJSON<T>(path: string): Promise<Result<T>> {
  await connection(); // request-time data: builds never depend on a live API
  const correlationId = crypto.randomUUID().replaceAll("-", "");
  let res: Response;
  try {
    res = await fetch(`${apiOrigin()}${path}`, {
      headers: { Accept: "application/json", "X-Correlation-ID": correlationId },
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new ApiUnavailableError("The learning service could not be reached.", correlationId);
  }
  if (res.status === 404) {
    return { ok: false, status: 404, problem: (await res.json()) as Problem };
  }
  if (!res.ok) {
    const problem = (await res.json().catch(() => null)) as Problem | null;
    throw new ApiUnavailableError(problem?.detail ?? `Service error (${res.status}).`, problem?.correlation_id ?? correlationId);
  }
  return { ok: true, data: (await res.json()) as T };
}

export const getCatalogue = cache(() => getJSON<Catalogue>("/v1/catalogue"));
export const getBookFor = cache((grade: number, subject: string) =>
  getJSON<Book>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/book`),
);
export const getChapter = cache((id: string) => getJSON<Chapter>(`/v1/chapters/${encodeURIComponent(id)}`));
export const searchCatalogue = cache((q: string, grade?: number) => {
  const params = new URLSearchParams({ q });
  if (grade) params.set("grade", String(grade));
  return getJSON<SearchResult>(`/v1/search?${params.toString()}`);
});
