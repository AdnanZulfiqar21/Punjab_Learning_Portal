import { expect, test } from "@playwright/test";

test("learner browses Class XII Biology to a chapter and its topics", async ({ page }) => {
  await page.goto("/learn");
  const xii = page.getByRole("region", { name: "Class XII", exact: true });
  await expect(xii).toBeVisible();
  await xii.getByRole("link", { name: /Biology/ }).click();

  await expect(page).toHaveURL(/\/learn\/12\/biology$/);
  await expect(page.getByRole("heading", { level: 1, name: "Biology" })).toBeVisible();
  // Class XII Biology continues the book's numbering from Class XI: it starts at Chapter 13.
  const first = page.getByRole("link", { name: /Chapter 13/ });
  await expect(first).toContainText("Thermoregulation");
  await first.click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thermoregulation");
  await expect(page.getByText("Class XII · Biology · Chapter 13")).toBeVisible();
  await expect(page.getByRole("note").filter({ hasText: "Textbook indexed" })).toBeVisible();
  const topics = page.getByRole("region", { name: "Topics" });
  await expect(topics.getByText("13.1", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /Next chapter/ })).toBeVisible();
});

test("Class XI and Class XII lists stay separate", async ({ page }) => {
  await page.goto("/learn");
  for (const [grade, count] of [
    ["Class XI", "16 chapters"],
    ["Class XII", "17 chapters"],
  ] as const) {
    const chem = page.getByRole("region", { name: grade, exact: true }).getByRole("link", { name: /Chemistry/ });
    await expect(chem).toContainText(count);
  }
});

test("search tolerates a typo and labels the class of each result", async ({ page }) => {
  await page.goto("/search");
  await page.getByLabel("Topic or chapter").fill("photosyntesis");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/q=photosyntesis/);
  const hit = page.getByRole("link", { name: /Photosynthesis/ }).first();
  await expect(hit).toContainText("Class XI · Biology");
});

test("unknown or out-of-scope catalogue URLs show an honest not-found page that is not indexable", async ({ page }) => {
  // With Cache Components the page shell streams first, so notFound() keeps HTTP 200 but adds noindex (Next 16 docs).
  for (const url of [
    "/learn/11/english",
    "/learn/10/physics",
    "/learn/chapter/not-a-uuid",
    "/learn/chapter/00000000-0000-4000-8000-000000000000",
  ]) {
    await page.goto(url);
    await expect(page.getByRole("heading", { name: "This page isn’t available" }), url).toBeVisible();
    await expect(page.locator('meta[name="robots"][content*="noindex"]').first(), url).toBeAttached();
  }
});

test("the maths alias resolves to the Class XI Mathematics book", async ({ page }) => {
  await page.goto("/learn/11/maths");
  await expect(page.getByRole("heading", { level: 1, name: "Mathematics" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Unit 7/ })).toContainText("Permutation");
});
