import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

// P14.S1.T3 (PRICING-01): the public pricing page shows what is on sale at its full price, what it covers and the
// purchase terms one finance person drafted and another published; there is no way to buy (payments aren't connected).
// Every product, amount and sentence of terms here is a labelled technical fixture, not a real offer or real terms.
const API = process.env.PORTAL_API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8100";
const AUTH = { timeout: 20_000 };

async function staff(browser: Browser, email: string): Promise<{ page: Page; token: string }> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("/signin?next=/account");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("studio-fixture-pass-1");
  await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/account$/, AUTH);
  return { page, token: (await ctx.cookies()).find((c) => c.name === "portal_session")!.value };
}

test.skip(({ isMobile }) => isMobile, "Staff journeys run on desktop; the public page is checked at phone width separately");

test("terms are drafted and published by two people, and the pricing page shows plans without a way to buy", async ({ browser, page, request }) => {
  const tag = crypto.randomUUID().slice(0, 6);
  const first = await staff(browser, "studio-finance@example.com");
  await first.page.goto("/admin/products");
  const draft = first.page.getByRole("form", { name: "Draft purchase terms" });
  for (const label of ["Taxes", "Renewal", "Buying during the free trial", "Refunds"]) {
    await draft.getByLabel(new RegExp(`^${label}`)).fill(`[FIXTURE ${tag}] ${label} wording for an end-to-end check.`);
  }
  await draft.getByRole("button", { name: "Save draft terms" }).click();
  await expect(first.page.getByText(/Your draft \(version \d+\) needs another finance person/)).toBeVisible(AUTH);
  await expect(first.page.getByRole("form", { name: "Publish the draft terms" })).toHaveCount(0); // not your own

  const second = await staff(browser, "studio-finance2@example.com");
  await second.page.goto("/admin/products");
  const publish = second.page.getByRole("form", { name: "Publish the draft terms" });
  await publish.getByLabel(/Why publish it/).fill("[FIXTURE] end-to-end two-person check");
  await publish.getByRole("button", { name: "Publish terms" }).click();
  await expect(second.page.getByText(/is on the pricing page\./)).toBeVisible(AUTH);

  // A priced plan, set up through the API as the same finance person.
  const h = { Authorization: `Bearer ${first.token}` };
  const code = `fx-price-${tag}`;
  const made = await (
    await request.post(`${API}/v1/admin/products`, {
      headers: h,
      data: { code, name: `[FIXTURE] Biology XI plan ${tag}`, kind: "subject_package", scope: { grades: [11], subjects: ["biology"] }, duration_days: 90, written_units: 2 },
    })
  ).json();
  await request.post(`${API}/v1/admin/products/${made.id}/activate`, { headers: h, data: { reason: "[FIXTURE] on sale for a test" } });
  await request.post(`${API}/v1/admin/products/${made.id}/prices`, { headers: h, data: { currency: "PKR", amount_minor: 199_900, reason: "[FIXTURE] price for a test" } });

  await page.goto("/pricing");
  await expect(page.getByRole("heading", { level: 1, name: "Plans and prices" })).toBeVisible();
  await expect(page.getByText("Buying isn't available yet")).toBeVisible();
  const plan = page.getByRole("list", { name: "Plans on sale" }).getByRole("listitem").filter({ hasText: code.slice(-6) });
  await expect(plan.getByText("PKR 1,999.00")).toBeVisible(AUTH);
  await expect(plan.getByText("Class XI Biology")).toBeVisible();
  await expect(plan.getByText("90 days (see the purchase terms below)")).toBeVisible();
  const terms = page.getByRole("region", { name: "Purchase terms" });
  await expect(terms.getByText(`[FIXTURE ${tag}] Refunds wording for an end-to-end check.`)).toBeVisible();
  await expect(page.getByRole("button", { name: /buy|checkout|pay/i })).toHaveCount(0); // nothing can be bought yet
  const axe = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
});
