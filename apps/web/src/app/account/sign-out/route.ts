// P19.S3.T3 (ISOLATION-01): signing out of a shared device. A plain form post, so the next page is a full load and
// nothing of the last person stays in this tab's memory (Cache Components otherwise keeps recent pages hidden in the
// document). The session ends on the server, the cookie goes, and the browser is told to clear what it keeps for this
// site. The sign-out form also clears storage itself, for browsers that ignore `Clear-Site-Data`. Cross-site posts are
// refused.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host || new URL(origin).host !== host) {
    return Response.json({ detail: "Cross-site sign-out refused." }, { status: 403 });
  }
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  if (token) {
    await fetch(`${readRuntimeConfig().apiOrigin}/v1/me/session`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    }).catch(() => undefined); // signing out of this browser must work even if the API can't be reached
  }
  store.delete(SESSION_COOKIE);
  return new Response(null, {
    status: 303,
    headers: { Location: "/", "Clear-Site-Data": '"cache", "storage"', "Cache-Control": "no-store" },
  });
}
