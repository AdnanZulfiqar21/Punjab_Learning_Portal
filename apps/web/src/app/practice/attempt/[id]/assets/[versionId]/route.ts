// A diagram from a question in the learner's own attempt (QUESTION-DIAGRAMS-01), fetched same-origin with the
// session. The API serves stem/option figures while answering and explanation figures once the result is available.
import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_req: Request, ctx: RouteContext<"/practice/attempt/[id]/assets/[versionId]">) {
  const { id, versionId } = await ctx.params;
  if (!UUID.test(id) || !UUID.test(versionId)) return new Response("File not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/attempts/${id}/assets/${versionId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) {
    const status = [401, 403, 404, 409].includes(upstream.status) ? upstream.status : 502;
    return new Response("This file isn't available.", { status, headers: { "Cache-Control": "private, no-store" } });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "image/png",
      "Cache-Control": "private, max-age=3600",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
