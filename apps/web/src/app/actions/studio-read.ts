"use server";

// Read-only helpers the studio's client components call (the API origin stays server-side).
import type { TopicNode } from "@portal/contracts";
import { getChapter } from "@/lib/api";

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
