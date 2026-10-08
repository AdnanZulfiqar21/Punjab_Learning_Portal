// Same-origin proxy for a clearer copy of one pending answer (W06.S2.T4). The learner's session is attached on the
// server; cross-site posts are refused. The API keeps the sealed original and stores this as a linked revision.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function POST(request: NextRequest, ctx: RouteContext<"/practice/written/[id]/questions/[position]/rescan">) {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) {
    return Response.json({ detail: "Cross-site upload refused." }, { status: 403 });
  }
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  const { id, position } = await ctx.params;
  if (!UUID.test(id) || !/^\d{1,2}$/.test(position) || !request.body) return Response.json({ detail: "Not found." }, { status: 404 });
  const note = (request.nextUrl.searchParams.get("note") ?? "").slice(0, 500);
  const upstream = await fetch(
    `${readRuntimeConfig().apiOrigin}/v1/written-attempts/${id}/questions/${position}/rescan?note=${encodeURIComponent(note)}`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/octet-stream",
        ...(request.headers.get("content-length") ? { "Content-Length": request.headers.get("content-length")! } : {}),
      },
      body: request.body,
      duplex: "half",
      signal: AbortSignal.timeout(120_000),
    } as RequestInit & { duplex: "half" },
  );
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });
}
