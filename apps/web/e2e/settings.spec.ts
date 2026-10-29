import { expect, test, type Browser, type Page } from "@playwright/test";

// P04.S3.T2 (SETTINGS-01): display settings belong to the device and are applied before the first paint; saved as the
// usual settings, they reach a new device at sign-in but never replace a device's own choice. Data saver holds lesson
// diagrams until tapped (the labelled structured-blocks fixture lesson from `portal-dev-seed-practice`).
const AUTH = { timeout: 20_000 };

test.skip(({ isMobile }) => isMobile && !process.env.E2E_FULL_MATRIX, "Account journeys run on desktop");

async function signIn(page: Page, email: string, register = false) {
  await page.goto("/signin?next=/account");
  if (register) await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("settings-fixture-pass-1");
  await page.getByRole("button", { name: register ? "Create account" : "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);
  await page.goto("/account");
  return page.getByRole("region", { name: "Display and data" });
}

async function newDevice(browser: Browser) {
  return (await browser.newContext()).newPage();
}

test("display settings apply at once, survive a reload and follow the learner to a new device", async ({ page, browser }) => {
  const email = `e2e-settings-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  const settings = await signIn(page, email, true);
  const root = page.locator("html");
  await settings.getByRole("radio", { name: "Dark" }).check();
  await settings.getByRole("radio", { name: "Larger" }).check();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await expect(root).toHaveAttribute("data-text-size", "larger");
  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "dark"); // set by the head script before the first paint
  await page.getByRole("region", { name: "Display and data" }).getByRole("button", { name: "Save as my usual settings" }).click();
  await expect(page.getByText("Saved as your usual settings.")).toBeVisible(AUTH);

  // A new device takes the usual settings when the learner signs in.
  const fresh = await newDevice(browser);
  await expect(await signIn(fresh, email)).toContainText("This device uses your usual settings.", AUTH);
  await expect(fresh.locator("html")).toHaveAttribute("data-theme", "dark");

  // A device that chose for itself keeps its choice.
  const own = await newDevice(browser);
  await own.goto("/");
  await own.context().addCookies([{ name: "portal-display", value: "light.default.0.0.1", url: new URL(own.url()).origin }]);
  await expect(await signIn(own, email)).toContainText("This device keeps its own display settings", AUTH);
  await expect(own.locator("html")).toHaveAttribute("data-theme", "light");
});

test("data saver holds lesson diagrams until tapped", async ({ page }) => {
  const email = `e2e-saver-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  const settings = await signIn(page, email, true);
  await settings.getByRole("checkbox", { name: /Data saver/ }).check();
  await page.goto("/learn");
  await page.getByRole("region", { name: "Class 11", exact: true }).getByRole("link", { name: /Biology/ }).click();
  await page.getByRole("link", { name: /Chapter 1(?!\d)/ }).first().click();
  const lessons = page.getByRole("region", { name: "Lessons" });
  const show = lessons.getByRole("button", { name: "Show diagram (data saver is on)" }).first();
  await expect(show).toBeVisible(AUTH);
  const before = await lessons.locator("img").count();
  await show.click();
  await expect(lessons.locator("img")).toHaveCount(before + 1);
});
