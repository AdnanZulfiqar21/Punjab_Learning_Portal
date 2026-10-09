"use server";

// P16.S3.T3: record source reviews and handle official syllabus notices. Nothing here changes content by itself.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/sources");
  return t;
}

type Out = { ok: boolean; error?: string };
const fail = (p: unknown, fallback: string): Out => {
  const prob = p as (Problem & { errors?: { msg: string }[] }) | null;
  return { ok: false, error: prob?.errors?.map((e) => e.msg).join(" ") || prob?.detail || fallback };
};

export async function reviewSource(id: string, note: string): Promise<Out> {
  const res = await api<null>(`/v1/studio/sources/${encodeURIComponent(id)}/review`, { method: "POST", token: await token(), body: JSON.stringify({ note }) });
  if (!res.ok) return fail(res.problem, "Couldn't record the review.");
  revalidatePath("/studio/sources");
  return { ok: true };
}

export async function logNotice(body: { grade: number; subject: string; title: string; source_url: string | null; summary: string }): Promise<Out> {
  const res = await api<unknown>("/v1/studio/syllabus-notices", { method: "POST", token: await token(), body: JSON.stringify(body) });
  if (!res.ok) return fail(res.problem, "Couldn't log the notice.");
  revalidatePath("/studio/sources");
  return { ok: true };
}

export async function decideNotice(id: string, accept: boolean, decision: string): Promise<Out> {
  const res = await api<unknown>(`/v1/studio/syllabus-notices/${encodeURIComponent(id)}/decision`, {
    method: "POST",
    token: await token(),
    body: JSON.stringify({ accept, decision }),
  });
  if (!res.ok) return fail(res.problem, "Couldn't record the decision.");
  revalidatePath("/studio/sources");
  return { ok: true };
}
