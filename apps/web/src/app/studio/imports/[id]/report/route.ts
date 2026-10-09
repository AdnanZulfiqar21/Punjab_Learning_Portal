// The correction report for an import (one CSV line per row), downloaded with the author's session.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const UUID = /^[0-9a-f-]{36}$/i;

export async function GET(_request: NextRequest, ctx: RouteContext<"/studio/imports/[id]/report">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { id } = await ctx.params;
  if (!UUID.test(id)) return new Response("Not found.", { status: 404 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/imports/${id}/report.csv`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) return new Response("Not found.", { status: upstream.status === 401 ? 401 : 404 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="import-${id}.csv"`,
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
