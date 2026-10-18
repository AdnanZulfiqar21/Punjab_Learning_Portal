import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

// LECTURE-READ-01: the lecture video through the site's own origin, so the browser's <video> can send the session
// cookie and range requests reach the API unchanged. The API decides who may watch; this route forwards nothing else.
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(req: Request, ctx: RouteContext<"/learn/lectures/[lectureId]/stream">) {
  const { lectureId } = await ctx.params;
  if (!UUID.test(lectureId)) return new Response("Not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to watch.", { status: 401, headers: { "Cache-Control": "private, no-store" } });
  const range = req.headers.get("range");
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/lectures/${lectureId}/stream`, {
    headers: { Authorization: `Bearer ${token}`, ...(range ? { Range: range } : {}) },
    cache: "no-store",
    signal: AbortSignal.timeout(120_000),
  });
  if (!upstream.ok && upstream.status !== 206) {
    const status = [401, 403, 404].includes(upstream.status) ? upstream.status : 502;
    return new Response("This lecture isn't available.", { status, headers: { "Cache-Control": "private, no-store" } });
  }
  const headers = new Headers({ "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Accept-Ranges": "bytes" });
  for (const name of ["content-type", "content-length", "content-range"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
