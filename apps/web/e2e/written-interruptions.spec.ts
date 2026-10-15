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

// W04.S2.T1 (WRITTEN-CONNECTION-01): an outage during a written test is explained, a page choice made offline is sent
// when the connection is back, submitting never hangs, and a changed device clock is corrected from the server's time.
test("offline, the written test says what it means, then saves the page map and corrects its clock", async ({ page, context }) => {
  test.slow();
  await page.clock.install(); // the device clock, which the learner (or a sleeping laptop) can change
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-offline-written-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);
  await page.goto("/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  await expect(page.getByRole("list", { name: "Uploaded pages" }).getByText("Page 1 · uploaded, not yet submitted")).toBeVisible(AUTH);

  // The clock: the device's time jumps 20 minutes ahead with no real time passing; a fresh server time corrects it.
  const left = async () => {
    const text = await page.getByText(/\(\d+:\d{2} left\)/).innerText();
    const [, m, s] = /\((\d+):(\d{2}) left\)/.exec(text)!;
    return Number(m) * 60 + Number(s);
  };
  await expect(page.getByText(/\(\d+:\d{2} left\)/)).toBeVisible(AUTH);
  const before = await left();
  await page.clock.setSystemTime(Date.now() + 20 * 60_000);
  await expect.poll(left, AUTH).toBeLessThan(before - 15 * 60);
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange"))); // back on this tab
  await expect.poll(left, AUTH).toBeGreaterThan(before - 5 * 60);

  // Offline: the notice says what an outage means; a page choice made now fails, and is sent once the connection is back.
  await context.setOffline(true);
  await expect(page.getByText("You're offline", { exact: true })).toBeVisible(AUTH);
  await expect(page.getByText(/Time keeps running: upload and submit by/)).toBeVisible();
  const parts = page.getByRole("group", { name: /^Question \d/ });
  await parts.nth(0).getByLabel("Page 1").check();
  await expect(page.getByRole("status").filter({ hasText: "Can't reach the service" })).toBeVisible(AUTH);
  for (let i = 1; i < (await parts.count()); i++) await parts.nth(i).getByLabel("Page 1").check();
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Can't reach the service" })).toBeVisible(AUTH); // refused, not hung
  await expect(page.getByRole("button", { name: "Submit for marking" })).toBeEnabled();

  await context.setOffline(false);
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  await expect(page.getByText("You're offline", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Submit for marking" }).click();
  await expect(page.getByText("Submitted for marking")).toBeVisible(AUTH);
});
