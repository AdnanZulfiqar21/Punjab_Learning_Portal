import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_req: Request, ctx: RouteContext<"/learn/topics/[topicId]/preview-assets/[versionId]">) {
  const { topicId, versionId } = await ctx.params;
  if (!UUID.test(topicId) || !UUID.test(versionId)) return new Response("File not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("File not found.", { status: 401, headers: { "Cache-Control": "private, no-store" } });
  const upstream = await fetch(
    `${readRuntimeConfig().apiOrigin}/v1/topics/${topicId}/preview-assets/${versionId}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(30_000) },
  );
  if (!upstream.ok) {
    const status = [401, 403, 404].includes(upstream.status) ? upstream.status : 502;
    return new Response("This file isn't available.", { status, headers: { "Cache-Control": "private, no-store" } });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? "inline",
    },
  });
}
