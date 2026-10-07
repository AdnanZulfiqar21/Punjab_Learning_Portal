// Shows a learner their own uploaded page. Private evidence: fetched with their session, never cached or shared.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function GET(_request: NextRequest, ctx: RouteContext<"/practice/written/[id]/pages/[pageId]">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { id, pageId } = await ctx.params;
  if (!UUID.test(id) || !UUID.test(pageId)) return new Response("Not found.", { status: 404 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/written-attempts/${id}/pages/${pageId}`, {
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
      "Content-Disposition": "inline",
    },
  });
}
