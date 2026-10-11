"use server";

// Read-only helpers the studio's client components call (the API origin stays server-side).
import type { TopicNode } from "@portal/contracts";
import { getChapter } from "@/lib/api";
import { api, sessionToken } from "@/lib/session";

export type TopicChoice = { id: string; number: string | null; title: string; depth: number };

function flatten(nodes: TopicNode[], out: TopicChoice[] = []): TopicChoice[] {
  for (const n of nodes) {
    out.push({ id: n.id, number: n.number ?? null, title: n.title, depth: n.depth });
    if (n.children?.length) flatten(n.children, out);
  }
  return out;
}

export async function chapterTopics(chapterId: string): Promise<TopicChoice[]> {
  if (!/^[0-9a-f-]{36}$/i.test(chapterId)) return [];
  const res = await getChapter(chapterId);
  return res.ok ? flatten(res.data.topics) : [];
}

export type SurfaceBlock = { type: string; [key: string]: unknown };
export type SurfaceReport = {
  version_number: number | null;
  oldest_client: { where: string; blocks: SurfaceBlock[] }[];
  fallback_blocks: number;
  issues: string[];
  access: { tier: string; meaning: string };
  languages: { present?: string[]; missing?: string[] };
};

/** P06.S3.T1 (SURFACES-01): the oldest-app rendering and what is still missing, for the last saved version. */
export async function itemSurfaces(itemId: string): Promise<SurfaceReport | null> {
  if (!/^[0-9a-f-]{36}$/i.test(itemId)) return null;
  const t = await sessionToken();
  if (!t) return null;
  const res = await api<SurfaceReport>(`/v1/studio/items/${itemId}/surfaces`, { token: t });
  return res.ok ? res.data : null;
}
