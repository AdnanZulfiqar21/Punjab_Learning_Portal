// Same-origin screenshot upload for a help request (P15.S3.T1). The server attaches the learner's session and streams
// the bytes to the API, which validates and re-encodes them in isolation. Cross-site posts are refused.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function POST(request: NextRequest, ctx: RouteContext<"/help/[id]/screenshots">) {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) {
    return Response.json({ detail: "Cross-site upload refused." }, { status: 403 });
  }
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  const { id } = await ctx.params;
  if (!UUID.test(id) || !request.body) return Response.json({ detail: "Not found." }, { status: 404 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/support/tickets/${id}/attachments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/octet-stream",
      ...(request.headers.get("content-length") ? { "Content-Length": request.headers.get("content-length")! } : {}),
    },
    body: request.body,
    duplex: "half",
    signal: AbortSignal.timeout(120_000),
  } as RequestInit & { duplex: "half" });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });
}
