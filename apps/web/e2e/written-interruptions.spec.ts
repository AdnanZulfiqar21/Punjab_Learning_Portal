import { expect, test } from "@playwright/test";

// W03.S3.T3 (UPLOAD-RETRY-01): interruption and concurrency while a written script is being prepared.
// * An upload lost to the network keeps its file on the device and can be sent again; it never adds a second page,
//   and choosing the same file again later is recognised as the same page.
// * Two tabs editing the page mapping get an explicit conflict, never a silent overwrite, and can load the latest.
// * A reload (app restart) shows exactly what the server holds.
// Technical fixture question and a labelled fixture account only.
const AUTH = { timeout: 20_000 };

test("a lost upload is retried without duplicates, and two tabs never overwrite each other's mapping", async ({ page, context }) => {
  test.slow();
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-interrupt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  const path = new URL(page.url()).pathname;
  const pagesList = page.getByRole("list", { name: "Uploaded pages" });

  // The connection drops during the upload: nothing is claimed, and the file waits on the device.
  const upload = /\/practice\/written\/[0-9a-f-]{36}\/upload$/;
  await page.route(upload, (route) => route.abort("internetdisconnected"));
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByText(/Connection lost\. Your file is kept on this device: try again\./)).toBeVisible(AUTH);
  await expect(pagesList.getByText(/^Page 1 ·/)).toHaveCount(0);
  await page.unroute(upload);
  await page.getByRole("button", { name: "Try synthetic-page.png again" }).click();
  await expect(pagesList.getByText("Page 1 · uploaded, not yet submitted")).toBeVisible(AUTH);

  // The same file chosen again is the same page, never a second one.
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByText("synthetic-page.png was already uploaded.")).toBeVisible(AUTH);
  await expect(pagesList.getByText(/^Page \d+ ·/)).toHaveCount(1);

  // Two tabs on the same script: the second, stale one is told, and loads the latest instead of overwriting it.
  const other = await context.newPage();
  await other.goto(path);
  const groups = (p: typeof page) => p.getByRole("group", { name: /^Question \d/ });
  await expect(groups(other).first()).toBeVisible(AUTH);
  await groups(page).nth(0).getByLabel("Page 1").check();
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision 1/ })).toBeVisible(AUTH);
  await groups(other).nth(1).getByLabel("I didn't answer this").check();
  await expect(other.getByRole("button", { name: "Load the latest mapping" })).toBeVisible(AUTH);
  await other.getByRole("button", { name: "Load the latest mapping" }).click();
  await expect(groups(other).nth(0).getByLabel("Page 1")).toBeChecked(AUTH); // the first tab's choice, kept
  await groups(other).nth(1).getByLabel("I didn't answer this").check();
  await expect(other.getByRole("status").filter({ hasText: /Saved · revision 2/ })).toBeVisible(AUTH);

  // A restart shows what the server holds: both choices, one page.
  await page.reload();
  await expect(groups(page).nth(0).getByLabel("Page 1")).toBeChecked(AUTH);
  await expect(groups(page).nth(1).getByLabel("I didn't answer this")).toBeChecked();
  await expect(pagesList.getByText(/^Page \d+ ·/)).toHaveCount(1);
});
