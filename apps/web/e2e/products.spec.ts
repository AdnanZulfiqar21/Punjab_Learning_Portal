import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// P14.S1.T1 (PRODUCTS-01): finance staff define a product, put it on sale and price it; the public listing shows the
// price on sale now in integer minor units. The product, its code and the amount are labelled technical fixtures, not a
// real offer or price; development-only staff accounts from `portal-dev-seed-staff`.
const API = process.env.PORTAL_API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8100";
const AUTH = { timeout: 20_000 };

test.skip(({ isMobile }) => isMobile, "Staff journeys run on desktop");

test("finance staff define, price and list a product", async ({ page, request }) => {
  await page.goto("/signin?next=/account");
  await page.getByLabel("Email").fill("studio-finance@example.com");
  await page.getByLabel("Password").fill("studio-fixture-pass-1");
  await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/account$/, AUTH);
  await page.getByRole("link", { name: "Products and prices" }).click();

  const code = `fx-e2e-${crypto.randomUUID().slice(0, 8)}`;
  const form = page.getByRole("form", { name: "New product" });
  await form.getByLabel("Code", { exact: true }).fill(code);
  await form.getByLabel("Name", { exact: true }).fill("[FIXTURE] Biology 11 package (not a real offer)");
  await form.getByLabel("Class 11", { exact: true }).check();
  await form.getByLabel("Biology", { exact: true }).check();
  await form.getByLabel("Written answers included").fill("4");
  await form.getByRole("button", { name: "Save draft product" }).click();

  const card = page.getByRole("listitem").filter({ hasText: code });
  await expect(card.getByText("Draft", { exact: true })).toBeVisible(AUTH);
  await expect(card.getByText("Subject package · Class 11 · Biology · 180 days · 4 written answers")).toBeVisible();
  const activate = card.getByRole("form", { name: "Put on sale" });
  await activate.getByLabel(/Why put it on sale/).fill("[FIXTURE] end-to-end check");
  await activate.getByRole("button", { name: "Put on sale" }).click();
  await expect(activate).toHaveCount(0, AUTH);

  const price = card.getByRole("form", { name: /Add a price for/ });
  await price.getByLabel("Amount").fill("2500.50");
  await expect(price.getByText("Will be stored as PKR 2,500.50 (250050 minor units).")).toBeVisible();
  await price.getByLabel(/Why this price/).fill("[FIXTURE] end-to-end check price");
  await price.getByRole("button", { name: "Add price version" }).click();
  await expect(card.getByText("Price history (1)")).toBeVisible(AUTH);
  await expect(card.getByText("Price now: PKR 2,500.50")).toBeVisible();

  const axe = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  const listed = (await (await request.get(`${API}/v1/products`)).json()) as { code: string; price: unknown }[];
  expect(listed.find((p) => p.code === code)?.price).toMatchObject({ currency: "PKR", amount_minor: 250050, on_sale: true, reason: null });
});
