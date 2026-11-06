// Server-side API client. The API origin is read from the runtime environment on every request, never baked into
// the build (roadmap §5.5: one immutable artifact promoted between environments).
import { cacheLife, cacheTag } from "next/cache";
import { connection } from "next/server";
import { cache } from "react";
import type { Book, Catalogue, Chapter, Discovery, Lesson, Problem, SearchResult, ServiceStatus } from "@portal/contracts";
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
  return fetchJSON<T>(path, token);
}

/** PUBLIC-CACHE-01: the catalogue tags; a publish or rollback in the Studio refreshes them at once. */
export const PUBLIC_CATALOGUE_TAG = "public-catalogue";

/** PUBLIC-CACHE-01: an anonymous, public API read (the same for every visitor, and already sent by the API as
 * `public, max-age=60`), shared by every page view on this server for up to a minute instead of one API call per view.
 * Never pass a session token here: personal and premium reads stay on `getJSON`. Callers reach it only after
 * `connection()`, so it runs at request time and never at build time. An error is not cached. */
async function publicJSON<T>(path: string, tag: string, seconds: number): Promise<Result<T>> {
  "use cache";
  cacheLife({ stale: seconds, revalidate: seconds, expire: 3600 });
  cacheTag(tag);
  return fetchJSON<T>(path);
}

async function getPublic<T>(path: string, tag = PUBLIC_CATALOGUE_TAG, seconds = 60): Promise<Result<T>> {
  await connection(); // request-time data: builds never depend on a live API
  return publicJSON<T>(path, tag, seconds);
}

async function fetchJSON<T>(path: string, token?: string): Promise<Result<T>> {
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

export const getCatalogue = cache(() => getPublic<Catalogue>("/v1/catalogue"));
/** P11.S1.T3 (DISCOVERY-01): what is published per book, filtered. Only known filter values are passed in. */
export const getDiscovery = cache((f: { grade?: string; track?: string; subject?: string; exam?: string; availability?: string }) => {
  const q = new URLSearchParams(Object.entries(f).filter((e): e is [string, string] => Boolean(e[1])));
  return getPublic<Discovery>(`/v1/discovery${q.size ? `?${q}` : ""}`);
});
export const getBookFor = cache((grade: number, subject: string) =>
  getPublic<Book>(`/v1/grades/${grade}/subjects/${encodeURIComponent(subject)}/book`),
);
export const getChapter = cache((id: string) => getPublic<Chapter>(`/v1/chapters/${encodeURIComponent(id)}`));
/** P15.S2.T3: known incidents for the banner on every page, shared for 30 seconds. */
export const getServiceStatus = cache(() => getPublic<ServiceStatus>("/v1/status", "service-status", 30));
/** Published, live lessons for a chapter. Premium bodies come back only for a learner with an active plan or
 * trial (review R07), so the learner's session is forwarded when present. */
export const getLessons = cache(async (chapterId: string, language?: string) =>
  getJSON<Lesson[]>(`/v1/chapters/${encodeURIComponent(chapterId)}/lessons${language ? `?language=${encodeURIComponent(language)}` : ""}`, await sessionToken()),
);
/** P11.S2.T3 (SEARCH-01): chapters, topics and published lessons. The learner's session is forwarded so lesson text
 * their plan covers can match; everyone else matches lessons by title only. */
export const searchContent = cache(async (q: string, grade?: number, subject?: string) => {
  const params = new URLSearchParams({ q, lessons: "true" });
  if (grade) params.set("grade", String(grade));
  if (subject) params.set("subject", subject);
  return getJSON<SearchResult>(`/v1/search?${params.toString()}`, await sessionToken());
});
