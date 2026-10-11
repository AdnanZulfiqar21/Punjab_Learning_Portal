// Same-origin asset upload (P07.S2.T4): streams the file to the API, which scans it, validates it in the isolated
// worker, archives the master and derives the delivery copy. Cross-site posts are refused; the token stays server-side.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest, ctx: RouteContext<"/studio/assets/[id]/upload">) {
  const { id } = await ctx.params;
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) {
    return Response.json({ detail: "Cross-site upload refused." }, { status: 403 });
  }
  if (!UUID.test(id)) return Response.json({ detail: "Asset not found." }, { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  if (!request.body) return Response.json({ detail: "Choose a file." }, { status: 422 });
  const qs = new URLSearchParams();
  for (const k of ["source", "author", "licence", "tool"]) qs.set(k, (request.nextUrl.searchParams.get(k) ?? "").slice(0, 500));
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/assets/${id}/versions?${qs.toString()}`, {
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
