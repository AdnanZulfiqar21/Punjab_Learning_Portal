import type { MetadataRoute } from "next";
import { connection } from "next/server";
import type { HelpArticleSummary } from "@portal/contracts";
import { getBookFor, getCatalogue } from "@/lib/api";
import { api } from "@/lib/session";
import { readRuntimeConfig } from "@/lib/runtime-config";

// P11.S1.T1 (PUBLIC-SITE-01): public pages only (home, learn, each book and chapter, help articles), built per request
// from the live catalogue. Empty outside production or without PORTAL_PUBLIC_ORIGIN, so staging is never advertised.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  await connection();
  const { role, publicOrigin } = readRuntimeConfig();
  if (role !== "production" || !publicOrigin) return [];
  const url = (path: string) => `${publicOrigin}${path}`;
  const out: MetadataRoute.Sitemap = [{ url: url("/") }, { url: url("/learn") }, { url: url("/help") }];
  const catalogue = await getCatalogue();
  if (catalogue.ok) {
    for (const g of catalogue.data.grades) {
      for (const { subject, books } of g.subjects) {
        if (!books.length) continue;
        out.push({ url: url(`/learn/${g.grade.number}/${subject.code}`) });
        const book = await getBookFor(g.grade.number, subject.code);
        if (book.ok) for (const ch of book.data.chapters) out.push({ url: url(`/learn/chapter/${ch.id}`) });
      }
    }
  }
  const articles = await api<HelpArticleSummary[]>("/v1/help/articles");
  if (articles.ok) for (const a of articles.data) out.push({ url: url(`/help/articles/${a.slug}`) });
  return out;
}
