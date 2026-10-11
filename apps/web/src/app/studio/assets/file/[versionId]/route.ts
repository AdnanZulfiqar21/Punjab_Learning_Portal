// Asset download for scoped staff (P07.S2.T4): the delivery copy, or the archived master as an attachment. The API
// rechecks scope; diagram sources are never offered inline.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, ctx: RouteContext<"/studio/assets/file/[versionId]">) {
  const { versionId } = await ctx.params;
  if (!UUID.test(versionId)) return new Response("Asset not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const copy = request.nextUrl.searchParams.get("copy") === "master" ? "master" : "delivery";
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/asset-versions/${versionId}/file?copy=${copy}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });
  if (!upstream.ok) {
    const problem = (await upstream.json().catch(() => null)) as { detail?: string } | null;
    const status = [401, 403, 404].includes(upstream.status) ? upstream.status : 502;
    return new Response(problem?.detail ?? "This file couldn't be downloaded.", { status, headers: { "Cache-Control": "private, no-store" } });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
