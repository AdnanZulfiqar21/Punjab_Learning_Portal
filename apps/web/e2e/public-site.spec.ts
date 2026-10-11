import { expect, test } from "@playwright/test";

// P11.S1.T1 (PUBLIC-SITE-01): the public home shows tracks and honest coverage from what is published; robots.txt is
// decided at request time by the runtime role (only production allows indexing, and never private pages).
const PRIVATE = ["/account", "/practice", "/study", "/studio", "/admin", "/notifications", "/onboarding"];

test("robots.txt never lets crawlers into private pages", async ({ request }) => {
  const res = await request.get("/robots.txt");
  expect(res.status()).toBe(200);
  const body = await res.text();
  expect(body).toMatch(/User-Agent: \*/i);
  const lines = body.split(/\r?\n/);
  if (lines.some((l) => /^Disallow: \/$/i.test(l.trim()))) return; // staging/development: nothing is indexed
  for (const p of PRIVATE) expect(lines.map((l) => l.trim()), p).toContain(`Disallow: ${p}`);
});

test("the sitemap is valid and lists only public pages", async ({ request }) => {
  const res = await request.get("/sitemap.xml");
  expect(res.status()).toBe(200);
  const xml = await res.text();
  expect(xml).toContain("<urlset");
  for (const p of PRIVATE) expect(xml).not.toContain(`${p}<`); // empty outside production; public pages only within it
});

test("the public home shows tracks and what is published so far", async ({ page }) => {
  await page.goto("/");
  const tracks = page.getByRole("region", { name: "Tracks and subjects" });
  await expect(tracks.getByRole("link", { name: "Pre-Medical" })).toBeVisible();
  await expect(tracks.getByRole("link", { name: "Pre-Engineering" })).toBeVisible();
  const coverage = page.getByRole("region", { name: "What is published so far" });
  await expect(coverage).toContainText(/reviewed lesson/);
  await tracks.getByRole("link", { name: "Pre-Engineering" }).click();
  await expect(page).toHaveURL(/\/learn\?track=pre_engineering$/);
  await expect(page.getByRole("region", { name: "Class XI", exact: true }).getByRole("link", { name: /Biology/ })).toHaveCount(0);
});
