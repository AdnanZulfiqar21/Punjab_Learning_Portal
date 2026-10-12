// Personal data download (P18.S3.T2), fetched with the signed-in person's session; audited by the API.
import { cookies } from "next/headers";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

export async function GET(request: Request) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/me/data-export`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });
  if (upstream.status === 403) {
    // P04.S3.T3 (REAUTH-01): the whole download needs a recent sign-in; sign in again and come straight back.
    const problem = (await upstream.json().catch(() => null)) as { title?: string } | null;
    if (problem?.title === "REAUTH_REQUIRED") return Response.redirect(new URL("/signin?next=/account/data-export&reason=reauth", request.url), 303);
  }
  if (!upstream.ok) return new Response("Your data couldn't be prepared. Please try again.", { status: upstream.status === 401 ? 401 : 502 });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? 'attachment; filename="my-data.json"',
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
