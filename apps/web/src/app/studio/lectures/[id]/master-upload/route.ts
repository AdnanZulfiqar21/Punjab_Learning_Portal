// MEDIA-UPLOAD-01 (P07.S2.T1): start a resumable master-video upload. Same-origin only; the token stays server-side.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest, ctx: RouteContext<"/studio/lectures/[id]/master-upload">) {
  const { id } = await ctx.params;
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) return Response.json({ detail: "Cross-site request refused." }, { status: 403 });
  if (!UUID.test(id)) return Response.json({ detail: "Lecture not found." }, { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/lectures/${id}/master-upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(await request.json().catch(() => ({}))),
    signal: AbortSignal.timeout(30_000),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });
}
