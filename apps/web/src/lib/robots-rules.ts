// P11.S1.T1 (PUBLIC-SITE-01): pure robots rules, so the production branch can be checked without a production host.
// Only production may be indexed, and never private pages (which also carry `noindex` themselves).
export const PRIVATE_PATHS = [
  "/account",
  "/practice",
  "/study",
  "/studio",
  "/admin",
  "/notifications",
  "/onboarding",
  "/signin",
  "/search",
  "/help/new",
  "/learn/lessons/",
];

export type RobotsRules = {
  rules: { userAgent: string; allow?: string; disallow: string | string[] };
  sitemap?: string;
};

export function robotsRules(role: string, publicOrigin?: string): RobotsRules {
  if (role !== "production") return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: { userAgent: "*", allow: "/", disallow: PRIVATE_PATHS },
    ...(publicOrigin ? { sitemap: `${publicOrigin}/sitemap.xml` } : {}),
  };
}
