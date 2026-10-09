// Storyboard prompt-package download (P07.S4.T1), fetched with the staff session. The API checks scope and audits it.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function GET(request: NextRequest, ctx: RouteContext<"/studio/items/[id]/prompt-package">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { id } = await ctx.params;
  if (!UUID.test(id)) return new Response("Not found.", { status: 404 });
  const version = request.nextUrl.searchParams.get("version") === "published" ? "published" : "working";
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/items/${id}/prompt-package?version=${version}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) return new Response("Not available.", { status: upstream.status === 401 ? 401 : upstream.status === 403 ? 403 : 404 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
