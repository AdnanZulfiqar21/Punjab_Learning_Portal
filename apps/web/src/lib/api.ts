// Server-side API client. The API origin is read from the runtime environment on every request, never baked into
// the build (roadmap §5.5: one immutable artifact promoted between environments).
import { connection } from "next/server";
import { cache } from "react";
import type { Book, Catalogue, Chapter, Lesson, Problem, SearchResult } from "@portal/contracts";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { sessionToken } from "@/lib/session";

export class ApiUnavailableError extends Error {
  constructor(
    message: string,
    readonly correlationId?: string | null,
  ) {
    super(message);
    this.name = "ApiUnavailableError";
  }
}

// 404 = never existed / not in the catalogue; 410 = intentionally retired from the catalogue (kept for history).
export type Result<T> = { ok: true; data: T } | { ok: false; status: 404 | 410; problem: Problem };

function apiOrigin(): string {
  return readRuntimeConfig().apiOrigin; // read per request from the process environment, never baked into the build
}

async function getJSON<T>(path: string, token?: string): Promise<Result<T>> {
  await connection(); // request-time data: builds never depend on a live API
  const correlationId = crypto.randomUUID().replaceAll("-", "");
  let res: Response;
  try {
    res = await fetch(`${apiOrigin()}${path}`, {
      headers: {
        Accept: "application/json",
        "X-Correlation-ID": correlationId,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store", // lesson responses can be personalised (R07); never kept in a shared data cache
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new ApiUnavailableError("The learning service could not be reached.", correlationId);
  }
  if (res.status === 404 || res.status === 410) {
    return { ok: false, status: res.status, problem: (await res.json()) as Problem };
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
/** Published, live lessons for a chapter. Premium bodies come back only for a learner with an active plan or
 * trial (review R07), so the learner's session is forwarded when present. */
export const getLessons = cache(async (chapterId: string, language?: string) =>
  getJSON<Lesson[]>(`/v1/chapters/${encodeURIComponent(chapterId)}/lessons${language ? `?language=${encodeURIComponent(language)}` : ""}`, await sessionToken()),
);
export const searchCatalogue = cache((q: string, grade?: number) => {
  const params = new URLSearchParams({ q });
  if (grade) params.set("grade", String(grade));
  return getJSON<SearchResult>(`/v1/search?${params.toString()}`);
});
