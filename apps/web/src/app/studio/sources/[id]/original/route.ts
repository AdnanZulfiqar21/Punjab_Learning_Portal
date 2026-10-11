// SOURCE-INTAKE-01 (P06.S2.T3): the owner's original source PDF, streamed to the API, which accepts only the bytes
// whose SHA-256 matches the registry. Same-origin only; the token stays server-side.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest, ctx: RouteContext<"/studio/sources/[id]/original">) {
  const { id } = await ctx.params;
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) return Response.json({ detail: "Cross-site upload refused." }, { status: 403 });
  if (!UUID.test(id)) return Response.json({ detail: "Source not found." }, { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  if (!request.body) return Response.json({ detail: "Choose the PDF." }, { status: 422 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/sources/${id}/original`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/pdf",
      ...(request.headers.get("content-length") ? { "Content-Length": request.headers.get("content-length")! } : {}),
    },
    body: request.body,
    duplex: "half",
    signal: AbortSignal.timeout(600_000),
  } as RequestInit & { duplex: "half" });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });
}
