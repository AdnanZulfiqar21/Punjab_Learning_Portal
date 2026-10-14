// Same-origin media pack upload (MEDIA-MANIFEST-01): streams the .zip to the API, which previews it (scans and
// validates every file, writes nothing) or, with commit=true, archives every file or none. Cross-site posts are
// refused; the token stays server-side.
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
  if (!request.body) return Response.json({ detail: "Choose a .zip file." }, { status: 422 });
  const commit = request.nextUrl.searchParams.get("commit") === "true" ? "true" : "false";
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/assets/manifest?commit=${commit}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/octet-stream",
      ...(request.headers.get("content-length") ? { "Content-Length": request.headers.get("content-length")! } : {}),
    },
    body: request.body,
    duplex: "half",
    signal: AbortSignal.timeout(300_000), // a pack can hold many files, each scanned and validated
  } as RequestInit & { duplex: "half" });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });
}
