// Portable content export download (P06.S4.T2): one class and subject as JSON, fetched with the publisher's session.
// The API enforces scope and MFA and audits every export.
import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { readRuntimeConfig } from "@/lib/runtime-config";
import { SESSION_COOKIE } from "@/lib/session";

const SUBJECTS = new Set(["biology", "chemistry", "physics", "computer_science", "mathematics"]);

export async function GET(request: NextRequest) {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return new Response("Sign in to continue.", { status: 401 });
  const grade = request.nextUrl.searchParams.get("grade");
  const subject = request.nextUrl.searchParams.get("subject") ?? "";
  if ((grade !== "11" && grade !== "12") || !SUBJECTS.has(subject)) return new Response("Choose a class and subject.", { status: 422 });
  const qs = new URLSearchParams({ grade, subject });
  const upstream = await fetch(`${readRuntimeConfig().apiOrigin}/v1/studio/export?${qs.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(120_000),
  });
  if (!upstream.ok) {
    const problem = (await upstream.json().catch(() => null)) as { detail?: string } | null;
    return new Response(problem?.detail ?? "The export isn't available.", { status: upstream.status === 401 ? 401 : upstream.status === 403 ? 403 : 404 });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? 'attachment; filename="content-export.json"',
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
