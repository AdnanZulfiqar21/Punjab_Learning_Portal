// A lesson's diagram or handout (P07.S1.T1), fetched same-origin. The API serves only files named by the lesson's
// published version, under its access tier: free previews for anyone, premium lessons with the learner's session.
import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_req: Request, ctx: RouteContext<"/learn/lessons/[id]/assets/[versionId]">) {
  const { id, versionId } = await ctx.params;
  if (!UUID.test(id) || !UUID.test(versionId)) return new Response("File not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/lessons/${id}/assets/${versionId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) {
    const status = [401, 403, 404].includes(upstream.status) ? upstream.status : 502;
    return new Response("This file isn't available.", { status, headers: { "Cache-Control": "private, no-store" } });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? "inline",
      // Premium files stay in the learner's own browser cache only; the session cookie decides access.
      "Cache-Control": token ? "private, max-age=3600" : (upstream.headers.get("cache-control") ?? "private, no-store"),
      "X-Content-Type-Options": "nosniff",
    },
  });
}
