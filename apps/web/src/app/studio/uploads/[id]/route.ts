// MEDIA-UPLOAD-01 (P07.S2.T1): an upload's state (the resume offset) and one chunk at a time, streamed to the API.
// Same-origin only for writes; the token stays server-side.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const relay = (upstream: Response) =>
  new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });

async function token() {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

export async function GET(_request: NextRequest, ctx: RouteContext<"/studio/uploads/[id]">) {
  const { id } = await ctx.params;
  if (!UUID.test(id)) return Response.json({ detail: "Upload not found." }, { status: 404 });
  const t = await token();
  if (!t) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  return relay(
    await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/uploads/${id}`, {
      headers: { Authorization: `Bearer ${t}` },
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    }),
  );
}

export async function PUT(request: NextRequest, ctx: RouteContext<"/studio/uploads/[id]">) {
  const { id } = await ctx.params;
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) return Response.json({ detail: "Cross-site upload refused." }, { status: 403 });
  if (!UUID.test(id)) return Response.json({ detail: "Upload not found." }, { status: 404 });
  const offset = request.nextUrl.searchParams.get("offset") ?? "";
  if (!/^\d{1,13}$/.test(offset)) return Response.json({ detail: "A chunk needs its byte offset." }, { status: 422 });
  const t = await token();
  if (!t) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  if (!request.body) return Response.json({ detail: "The chunk is empty." }, { status: 422 });
  return relay(
    await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/uploads/${id}?offset=${offset}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${t}`,
        "Content-Type": "application/octet-stream",
        ...(request.headers.get("content-length") ? { "Content-Length": request.headers.get("content-length")! } : {}),
      },
      body: request.body,
      duplex: "half",
      signal: AbortSignal.timeout(300_000),
    } as RequestInit & { duplex: "half" }),
  );
}
