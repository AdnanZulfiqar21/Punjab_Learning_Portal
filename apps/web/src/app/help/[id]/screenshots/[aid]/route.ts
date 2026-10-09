// A help-request screenshot, for its owner or for staff who can see the request (the API decides). Private: fetched
// with the viewer's session, never cached or shared.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function GET(_request: NextRequest, ctx: RouteContext<"/help/[id]/screenshots/[aid]">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { id, aid } = await ctx.params;
  if (!UUID.test(id) || !UUID.test(aid)) return new Response("Not found.", { status: 404 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/support/tickets/${id}/attachments/${aid}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) return new Response("Not found.", { status: upstream.status === 401 ? 401 : 404 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
      "Content-Disposition": "inline",
    },
  });
}
