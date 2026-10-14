import { expect, test } from "@playwright/test";
import { audit } from "./helpers/a11y";

// P04.S2.T3 (ACCESS-GRANTS-01): finance grants a learner pilot access from the web, sees it with its written units,
// and revokes it with a reason. Labelled fixture accounts only.
const AUTH = { timeout: 20_000 };

test.skip(({ isMobile }) => isMobile, "Staff screens run on desktop");

test("finance grants and revokes pilot access from the web", async ({ page, browser }) => {
  test.slow();
  const email = `e2e-grant-${Date.now()}@example.com`;
  const learner = await (await browser.newContext()).newPage();
  await learner.goto("/signin?next=/account");
  await learner.getByRole("button", { name: "New here? Create an account" }).click();
  await learner.getByLabel("Email").fill(email);
  await learner.getByLabel("Password").fill("practice-fixture-pass-1");
  await learner.getByRole("button", { name: "Create account" }).click();
  await expect(learner).toHaveURL(/:\d+\/account$/, AUTH);

  await page.goto("/signin?next=/admin/access");
  await page.getByLabel("Email").fill("studio-finance@example.com");
  await page.getByLabel("Password").fill("studio-fixture-pass-1"); // pragma: allowlist secret (dev-seed fixture)
  await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/admin\/access$/, AUTH);
  await audit(page, null);

  const form = page.getByRole("form", { name: "Grant access" });
  await form.getByLabel("Learner email").fill(email);
  await form.getByLabel("Kind of access").selectOption("pilot");
  await form.getByLabel("Days").fill("7");
  await form.getByLabel("Written units").fill("6");
  await form.getByLabel("Reason (kept on the record)").fill("Fixture: e2e pilot cohort member");
  await form.getByRole("button", { name: "Grant access" }).click();
  await expect(form.getByText("Access granted.")).toBeVisible(AUTH);
  const item = page.getByRole("list", { name: "Active access grants" }).getByRole("listitem").filter({ hasText: email });
  await expect(item).toContainText("Pilot");
  await expect(item).toContainText("Written units: 0 used, 0 held for unmarked tests, of 6");

  await learner.goto("/account");
  await expect(learner.getByText(/Pilot access until/)).toBeVisible(AUTH);

  await item.getByRole("button", { name: "Revoke…" }).click();
  await item.getByLabel(/Why revoke it\?/).fill("Fixture: left the pilot cohort");
  await item.getByRole("button", { name: "Revoke", exact: true }).click();
  await expect(page.getByRole("list", { name: "Active access grants" }).getByText(email)).toHaveCount(0, AUTH);
});
