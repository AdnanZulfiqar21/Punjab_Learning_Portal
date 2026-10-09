// Same-origin import upload (P06.S2): streams the file to the API, which previews it (a dry run that writes no
// content). The session token never reaches browser JavaScript; cross-site posts are refused.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) {
    return Response.json({ detail: "Cross-site upload refused." }, { status: 403 });
  }
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Sign in to continue." }, { status: 401 });
  const format = request.nextUrl.searchParams.get("format") === "csv" ? "csv" : "json";
  const filename = (request.nextUrl.searchParams.get("filename") ?? "import").slice(0, 200);
  if (!request.body) return Response.json({ detail: "Choose a file." }, { status: 422 });
  const qs = new URLSearchParams({ format, filename });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/imports?${qs.toString()}`, {
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
