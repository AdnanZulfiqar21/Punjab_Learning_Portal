// SOURCE-INTAKE-01 (P06.S2.T3): one page of a stored source original as an image, for content staff in its class and
// subject (the API renders it in an isolated worker; the PDF itself is never served).
import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_req: Request, ctx: RouteContext<"/studio/sources/[id]/pages/[page]">) {
  const { id, page } = await ctx.params;
  if (!UUID.test(id) || !/^\d{1,4}$/.test(page)) return new Response("Page not found.", { status: 404 });
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/sources/${id}/pages/${page}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(45_000),
  });
  if (!upstream.ok) {
    const problem = (await upstream.json().catch(() => null)) as { detail?: string } | null;
    return new Response(problem?.detail ?? "This page isn't available.", {
      status: [401, 403, 404].includes(upstream.status) ? upstream.status : 502,
      headers: { "Cache-Control": "private, no-store", "Content-Type": "text/plain; charset=utf-8" },
    });
  }
  return new Response(upstream.body, {
    headers: { "Content-Type": "image/png", "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff" },
  });
}
