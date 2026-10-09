// Export download (P16.S4.T2), fetched with the signed-in person's session. The API rechecks ownership, permission and
// result release, and audits the download; nothing is cached on the way through.
import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_req: Request, ctx: RouteContext<"/account/exports/[id]/download">) {
  const { id } = await ctx.params;
  if (!UUID.test(id)) return new Response("Export not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/exports/${id}/download`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });
  if (!upstream.ok) {
    const problem = (await upstream.json().catch(() => null)) as { detail?: string } | null;
    const status = [401, 403, 404, 409].includes(upstream.status) ? upstream.status : 502;
    return new Response(problem?.detail ?? "This export couldn't be downloaded.", { status, headers: { "Cache-Control": "private, no-store" } });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? 'attachment; filename="export"',
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
