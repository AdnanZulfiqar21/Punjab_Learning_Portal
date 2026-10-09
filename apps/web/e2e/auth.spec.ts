import { expect, test, type Page } from "@playwright/test";

// Uses the development identity adapter, which the API exposes only in development/test roles.
// Each test registers a fresh technical-fixture account; no real personal data.
const newEmail = (tag: string) => `e2e-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
const PASSWORD = "e2e-fixture-password-1";
// Registration + sign-in run two deliberate argon2 hashes; under parallel test load that can exceed the 5 s default.
const AUTH = { timeout: 20_000 };

async function register(page: Page, email: string, next = "/account") {
  await page.goto(`/signin?next=${encodeURIComponent(next)}`);
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
}

test("protected pages redirect to sign-in and return afterwards", async ({ page }) => {
  await page.goto("/account");
  await expect(page).toHaveURL(/\/signin\?next=(%2F|\/)account$/);
  await page.goto("/onboarding");
  await expect(page).toHaveURL(/\/signin\?next=(%2F|\/)onboarding$/);
  await register(page, newEmail("redirect"), "/onboarding");
  await expect(page).toHaveURL(/\/onboarding$/, AUTH);
  await expect(page.getByRole("heading", { name: "Set up your learning" })).toBeVisible();
});

test("register, onboard, see the profile and session, then sign out", async ({ page }) => {
  const email = newEmail("journey");
  await register(page, email);
  await expect(page).toHaveURL(/\/account$/, AUTH);
  await expect(page.getByRole("heading", { name: email })).toBeVisible();
  await expect(page.getByText("Finish setting up")).toBeVisible();
  await expect(page.getByText("This device", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Account", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Set up learning preferences" }).click();
  await page.getByLabel("Class XII").check();
  await page.getByLabel("Physics").check();
  await page.getByLabel("Mathematics").check();
  await page.getByLabel("ECAT").check();
  await page.getByLabel("Minutes per day").fill("60");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page).toHaveURL(/\/learn$/);

  await page.goto("/account");
  await expect(page.getByText("physics, mathematics")).toBeVisible();
  await expect(page.getByText("ECAT")).toBeVisible();
  await expect(page.getByText("60 minutes")).toBeVisible();

  await page.getByRole("button", { name: "Sign out of this device" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  await page.goto("/account");
  await expect(page).toHaveURL(/\/signin/);
});

test("wrong password is rejected without revealing whether the account exists", async ({ page }) => {
  await page.goto("/signin");
  await page.getByLabel("Email").fill(newEmail("unknown"));
  await page.getByLabel("Password").fill("not-the-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("Email or password is incorrect.", AUTH);
});

test("a second device can be signed out from the first", async ({ browser }) => {
  const email = newEmail("devices");
  const a = await (await browser.newContext()).newPage();
  await register(a, email);
  await expect(a).toHaveURL(/\/account$/, AUTH);

  const bCtx = await browser.newContext();
  const b = await bCtx.newPage();
  await b.goto("/signin");
  await b.getByLabel("Email").fill(email);
  await b.getByLabel("Password").fill(PASSWORD);
  await b.getByRole("button", { name: "Sign in" }).click();
  await expect(b).toHaveURL(/\/account$/, AUTH);

  await a.reload();
  await expect(a.getByRole("button", { name: "Sign out", exact: true })).toHaveCount(1);
  await a.getByRole("button", { name: "Sign out everywhere else" }).click();
  await expect(a.getByRole("button", { name: "Sign out", exact: true })).toHaveCount(0);

  await b.goto("/account");
  await expect(b).toHaveURL(/\/signin/);
  await bCtx.close();
});

test("sign-in ignores off-site return addresses", async ({ page }) => {
  await register(page, newEmail("redirect-safe"), "//evil.example.com/");
  await expect(page).toHaveURL(/localhost:\d+\/account$/, AUTH);
});

for (const sneaky of ["/\t/evil.example.com/", "/\n/evil.example.com/", "/\\evil.example.com/", " //evil.example.com/"]) {
  test(`sign-in ignores a disguised off-site return address (${JSON.stringify(sneaky)})`, async ({ page }) => {
    // Browsers drop tabs and newlines inside URLs and treat backslashes as slashes, so these become //evil… .
    await register(page, newEmail("redirect-sneaky"), sneaky);
    await expect(page).toHaveURL(/localhost:\d+\/account$/, AUTH);
  });
}
