"use server";

// P15.S2.T1: help-centre staff draft articles (a new immutable version per save) and publish them with MFA.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import type { Problem, StaffHelpArticle } from "@portal/contracts";
import { api, sessionToken } from "@/lib/session";

async function token(): Promise<string> {
  const t = await sessionToken();
  if (!t) redirect("/signin?next=/studio/help");
  return t;
}

export type HelpDraftState = { ok?: boolean; error?: string } | undefined;

export async function saveHelpDraft(_prev: HelpDraftState, form: FormData): Promise<HelpDraftState> {
  const res = await api<StaffHelpArticle>("/v1/studio/help/articles", {
    method: "PUT",
    token: await token(),
    body: JSON.stringify({
      slug: String(form.get("slug") ?? "").trim(),
      locale: String(form.get("locale") ?? "en"),
      title: String(form.get("title") ?? ""),
      summary: String(form.get("summary") ?? ""),
      markdown: String(form.get("markdown") ?? ""),
      tags: String(form.get("tags") ?? "")
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    }),
  });
  if (!res.ok) {
    const p = res.problem as (Problem & { errors?: string[] }) | null;
    return { error: [p?.detail ?? "Couldn't save the draft.", ...(p?.errors ?? [])].join(" ") };
  }
  revalidatePath("/studio/help");
  return { ok: true };
}

export async function publishHelp(id: string, action: "publish" | "retire"): Promise<{ error?: string }> {
  const res = await api<StaffHelpArticle>(`/v1/studio/help/articles/${encodeURIComponent(id)}/${action}`, { method: "POST", token: await token() });
  revalidatePath("/studio/help");
  return res.ok ? {} : { error: (res.problem as Problem | null)?.detail ?? `Couldn't ${action} the article.` };
}
