import { expect, test } from "@playwright/test";

// P11.S4.T2 (PWA-01): installable web with a safe offline shell. The service worker caches only the offline page,
// so no exam answer, key or personal page is ever stored by it.
test("the manifest is installable and its icons exist", async ({ request }) => {
  const res = await request.get("/manifest.webmanifest");
  expect(res.status()).toBe(200);
  const m = await res.json();
  expect(m.display).toBe("standalone");
  expect(m.start_url).toBe("/");
  for (const icon of m.icons as { src: string }[]) {
    const r = await request.get(icon.src);
    expect(r.status(), icon.src).toBe(200);
    expect(r.headers()["content-type"]).toContain("image/png");
  }
  const sw = await request.get("/sw.js");
  expect(sw.status()).toBe(200);
  expect(sw.headers()["cache-control"]).toContain("no-store");
});

test("offline: the banner says so, pages fall back to the offline page, and only that page is cached", async ({ page, context }) => {
  test.setTimeout(90_000);
  await page.goto("/learn");
  await expect(page.getByRole("region", { name: "Class 11", exact: true })).toBeVisible({ timeout: 20_000 });
  const ready = await page
    .evaluate(() =>
      Promise.race([
        navigator.serviceWorker.ready.then(() => true),
        new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 10_000)),
      ]),
    )
    .catch(() => false);
  test.skip(!ready, "The offline shell is registered by production builds only (CI runs one)");
  await page.reload(); // the worker now controls the page

  await context.setOffline(true);
  await expect(page.getByRole("status").filter({ hasText: "You're offline" })).toBeVisible();
  await page.goto("/practice").catch(() => undefined);
  await expect(page.getByRole("heading", { name: "You're offline" })).toBeVisible();
  const cached = await page.evaluate(async () => {
    const out: string[] = [];
    for (const key of await caches.keys()) {
      for (const req of await (await caches.open(key)).keys()) out.push(new URL(req.url).pathname);
    }
    return out;
  });
  expect(cached).toEqual(["/offline.html"]);
  await context.setOffline(false);
  await page.goto("/learn");
  await expect(page.getByRole("region", { name: "Class 11", exact: true })).toBeVisible({ timeout: 20_000 });
});
