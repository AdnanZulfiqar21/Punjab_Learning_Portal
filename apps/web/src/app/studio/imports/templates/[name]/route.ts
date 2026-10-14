// The multiple-choice import template (headings only), downloaded with the author's session (IMPORT-XLSX-01).
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const TYPES: Record<string, string> = {
  "mcq.xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "mcq.csv": "text/csv; charset=utf-8",
};

export async function GET(_request: NextRequest, ctx: RouteContext<"/studio/imports/templates/[name]">) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const { name } = await ctx.params;
  if (!Object.hasOwn(TYPES, name)) return new Response("Not found.", { status: 404 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/imports/templates/${name}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  if (!upstream.ok) return new Response("Not available.", { status: upstream.status === 401 ? 401 : upstream.status === 403 ? 403 : 404 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": TYPES[name],
      "Content-Disposition": `attachment; filename="${name.replace(".", "-template.")}"`,
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
