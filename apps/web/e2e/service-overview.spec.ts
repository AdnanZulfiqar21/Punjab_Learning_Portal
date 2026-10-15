import { expect, test } from "@playwright/test";
import { audit } from "./helpers/a11y";

// The operator's service overview (OPS-01, STAFFING-01, LIFECYCLE-01) with the labelled dev-seed operator account.
const AUTH = { timeout: 20_000 };
const PASSWORD = "studio-fixture-pass-1"; // pragma: allowlist secret (dev-seed fixture, refused outside development/test)

test.skip(({ isMobile }) => isMobile, "Staff screens run on desktop");

test("an operator sees the written script lifecycle with the count behind every time", async ({ page }) => {
  await page.goto("/signin?next=/admin/service");
  await page.getByLabel("Email").fill("studio-operator@example.com");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByLabel(/Simulate a multi-factor sign-in/).check();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/admin\/service$/, AUTH);
  const lifecycle = page.getByRole("region", { name: "Written scripts, last 30 days" });
  await expect(lifecycle).toBeVisible(AUTH);
  await expect(lifecycle.getByRole("list", { name: "Script outcomes" })).toContainText("Released automatically: 0");
  const table = lifecycle.getByRole("table", { name: "Lifecycle stage times" });
  for (const stage of ["Upload while writing (per page)", "Start to submission", "Waiting for a teacher", "Teacher marking (elapsed)", "Submission to result"]) {
    await expect(table.getByRole("rowheader", { name: stage })).toBeVisible();
  }
  await expect(table.getByRole("columnheader", { name: "Count" })).toBeVisible();
  await expect(lifecycle.getByText(/Not measured yet: reading: .*\(B10\)/)).toBeVisible();
  await audit(page, null);
});
