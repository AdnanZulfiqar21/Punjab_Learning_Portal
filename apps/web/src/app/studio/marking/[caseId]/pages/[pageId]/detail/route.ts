// Higher-detail rendition of a submitted page (OCT8-06), rendered by the API from the immutable original for markers
// in scope. Optional ?region=x,y,w,h (page fractions). Private, never cached; provenance headers are passed through.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;
const REGION = /^[0-9.]+,[0-9.]+,[0-9.]+,[0-9.]+$/;

export async function GET(request: NextRequest, ctx: RouteContext<"/studio/marking/[caseId]/pages/[pageId]/detail">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { caseId, pageId } = await ctx.params;
  if (!UUID.test(caseId) || !UUID.test(pageId)) return new Response("Not found.", { status: 404 });
  const region = request.nextUrl.searchParams.get("region");
  if (region !== null && !REGION.test(region)) return new Response("Invalid region.", { status: 422 });
  const qs = region ? `?region=${encodeURIComponent(region)}` : "";
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/written/cases/${caseId}/pages/${pageId}/detail${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });
  if (!upstream.ok) return new Response(upstream.status === 503 ? "Busy, try again." : "Not found.", { status: upstream.status === 401 ? 401 : upstream.status === 503 ? 503 : 404 });
  const headers: Record<string, string> = {
    "Content-Type": "image/png",
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  };
  for (const h of ["x-evidence-sha256", "x-evidence-page", "x-derivative"]) {
    const v = upstream.headers.get(h);
    if (v) headers[h] = v;
  }
  return new Response(upstream.body, { headers });
}
