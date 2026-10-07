// Submitted evidence for markers in scope (the API checks the reviewer's scope). Private and never cached.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function GET(_request: NextRequest, ctx: RouteContext<"/studio/marking/[caseId]/pages/[pageId]">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { caseId, pageId } = await ctx.params;
  if (!UUID.test(caseId) || !UUID.test(pageId)) return new Response("Not found.", { status: 404 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/written/cases/${caseId}/pages/${pageId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) return new Response("Not found.", { status: upstream.status === 401 ? 401 : 404 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
