import { expect, test, type Browser, type Page } from "@playwright/test";
import { audit, reflows } from "./helpers/a11y";

// W07.S3.T1: reading and navigating written practice. A learner maps and submits pages with the keyboard alone, with a
// visible focus ring; the builder, the script and the released result have no serious axe violations and reflow at
// 200 % zoom (640 px); statuses are words, not colours alone; a teacher's comment in Urdu is laid out right to left;
// page scans load lazily at a fixed size. Technical fixture question, labelled fixture accounts and dev-seed staff only.
// Not covered here: equations in written questions (no reviewed written fixture has one) and screen-reader listening,
// which a person still has to do (P19.S2.T3).
const AUTH = { timeout: 20_000 };
const URDU = "یہ جانچ کا نمونہ ہے"; // a fixture comment ("this is a test sample"), not academic content

test.skip(({ isMobile }) => isMobile, "Staff marking runs on desktop; reflow is checked at 640 px below");

async function focusRing(page: Page) {
  const style = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return el ? getComputedStyle(el).outlineStyle : "none";
  });
  expect(style, "the focused control shows a focus ring").not.toBe("none");
}

async function teacher(browser: Browser): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await page.goto(`/signin?next=${encodeURIComponent("/studio/marking")}`);
  await page.getByLabel("Email").fill("studio-reviewer@example.com");
  await page.getByLabel("Password").fill("studio-fixture-pass-1"); // pragma: allowlist secret (dev-seed fixture)
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/:\d+\/studio\/marking$/, AUTH);
  return page;
}

test("written practice reads, navigates and reflows accessibly", async ({ page, browser }) => {
  test.slow();
  await page.goto("/signin?next=/practice?grade=11%26subject=biology");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-written-a11y-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("practice-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\?/, AUTH);
  await page.getByRole("button", { name: "Start my free 30-day trial" }).click();
  await expect(page.getByText(/Free trial until/)).toBeVisible(AUTH);

  await audit(page, "/practice/written?grade=11&subject=biology");
  await page.getByRole("group", { name: "Chapters" }).getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Start written test" }).click();
  await expect(page).toHaveURL(/:\d+\/practice\/written\/[0-9a-f-]{36}$/, AUTH);
  const path = new URL(page.url()).pathname;
  const attemptId = path.split("/").pop()!;
  await page.getByLabel("Add photos or a PDF").setInputFiles("e2e/fixtures/synthetic-page.png");
  const uploaded = page.getByRole("list", { name: "Uploaded pages" });
  await expect(uploaded.getByText("Page 1 · uploaded, not yet submitted")).toBeVisible(AUTH); // a word, not a colour
  const scan = uploaded.getByRole("img", { name: "Page 1" });
  await expect(scan).toHaveAttribute("loading", "lazy");
  expect((await scan.boundingBox())!.height).toBeGreaterThan(100); // a fixed box: nothing jumps when it loads
  await audit(page, null);

  // Keyboard only: tick "Page 1" for every part, then submit.
  const boxes = page.getByRole("group", { name: /^Question \d/ }).getByLabel("Page 1");
  for (let i = 0; i < (await boxes.count()); i++) {
    await boxes.nth(i).focus();
    await page.keyboard.press("Space");
    await expect(boxes.nth(i)).toBeChecked();
  }
  await expect(page.getByRole("status").filter({ hasText: /Saved · revision \d+/ })).toBeVisible(AUTH);
  const submit = page.getByRole("button", { name: "Submit for marking" });
  await submit.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab"); // arrive by keyboard so :focus-visible applies
  await expect(submit).toBeFocused();
  await focusRing(page);
  await page.keyboard.press("Enter");
  await expect(page.getByText(/^Receipt [0-9a-f]{8} ·/)).toBeVisible(AUTH);
  await expect(uploaded.getByText("Page 1 · submitted")).toBeVisible();

  // A teacher marks it, writing one comment in Urdu.
  const marker = await teacher(browser);
  await marker.getByRole("link", { name: `Script ${attemptId.slice(0, 8)}` }).click();
  await marker.getByRole("button", { name: "Start marking" }).click();
  await marker.getByRole("radiogroup", { name: "Award for a1" }).getByLabel("1", { exact: true }).check();
  await marker.getByLabel("Reason for a1").fill(URDU);
  await marker.getByRole("button", { name: "Release result" }).click();
  await expect(marker.getByText("Result released")).toBeVisible(AUTH);

  await page.reload();
  const comment = page.getByText(URDU, { exact: true });
  await expect(comment).toBeVisible(AUTH);
  expect(await comment.evaluate((el) => getComputedStyle(el).direction)).toBe("rtl");
  await expect(page.getByText(/^Question 1: 1 \/ \d+$/)).toBeVisible(); // marks in words and numbers
  await audit(page, null);

  // 200 % zoom: the same script and result at 640 px.
  await page.setViewportSize({ width: 640, height: 900 });
  await page.reload();
  await expect(comment).toBeVisible(AUTH);
  await reflows(page);
  await page.goto("/practice/written?grade=11&subject=biology");
  await expect(page.getByRole("button", { name: "Start written test" })).toBeVisible(AUTH);
  await reflows(page);
});
