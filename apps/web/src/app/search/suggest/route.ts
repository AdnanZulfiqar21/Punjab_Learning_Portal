// SEARCH-SUGGEST-01 (owner, 2026-11-13): suggestions under the search box while the learner types. The chapters and
// topics whose titles match (the API's catalogue search without lessons: public, no session needed), a few at a time.
import type { NextRequest } from "next/server";
import type { SearchResult } from "@portal/contracts";
import { readRuntimeConfig } from "@/lib/runtime-config";
import type { Suggestion } from "@/lib/search-suggest";

const LIMIT = 8;

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const q = (sp.get("q") ?? "").trim().slice(0, 100);
  if (q.length < 2) return Response.json({ items: [] });
  const params = new URLSearchParams({ q, limit: String(LIMIT) });
  const grade = sp.get("grade");
  if (grade === "11" || grade === "12") params.set("grade", grade);
  const subject = sp.get("subject");
  if (subject && /^[a-z_]{2,40}$/.test(subject)) params.set("subject", subject);
  let res: Response;
  try {
    res = await fetch(`${readRuntimeConfig().apiOrigin}/v1/search?${params.toString()}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
  } catch {
    return Response.json({ items: [] }, { status: 502 });
  }
  if (!res.ok) return Response.json({ items: [] }, { status: res.status === 422 ? 200 : 502 });
  const data = (await res.json()) as SearchResult;
  const items: Suggestion[] = data.hits
    .filter((h) => h.kind === "chapter" || h.kind === "topic")
    .map((h) => ({
      kind: h.kind as Suggestion["kind"],
      id: h.id,
      chapter_id: h.chapter_id,
      title: h.title,
      number: h.number ?? null,
      chapter_title: h.chapter_title,
      grade: h.grade,
      subject_code: h.subject_code,
      subject_name: h.subject_name,
    }));
  return Response.json({ items }, { headers: { "Cache-Control": "public, max-age=60" } });
}
