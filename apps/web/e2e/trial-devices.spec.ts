import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// P04.S1.T3: the devices using a learner's free trial are listed on the account page and can be removed after a second
// confirmation. The "phone" is a labelled technical fixture registered through the API's development/test evidence
// adapter with a made-up installation token; it is not a real device and says nothing about device verification.
const API = process.env.PORTAL_API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8100";
const AUTH = { timeout: 20_000 };
const hex = () => crypto.randomUUID().replaceAll("-", "");

test.skip(({ isMobile }) => isMobile && !process.env.E2E_FULL_MATRIX, "Account journeys run on desktop");

test("a learner sees the devices on their free trial and removes one", async ({ page, request, context }) => {
  await page.goto("/signin?next=/account");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-trial-devices-${hex().slice(0, 12)}@example.com`);
  await page.getByLabel("Password").fill("trial-devices-fixture-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/(account|onboarding)/, AUTH);

  const session = (await context.cookies()).find((c) => c.name === "portal_session");
  expect(session).toBeTruthy();
  const claim = await request.post(`${API}/v1/me/trial/claims`, {
    headers: { Authorization: `Bearer ${session!.value}`, "X-Portal-Client": "native", "X-Portal-Install": `fixture-install-${hex()}` },
    data: { surface: "android", idempotency_key: hex(), proof: { fixture_verdict: "clean" }, label: "Fixture phone" },
  });
  expect((await claim.json()).state).toBe("granted");

  await page.goto("/account");
  const section = page.getByRole("region", { name: "Devices on your free trial" });
  await expect(section.getByText("Fixture phone")).toBeVisible(AUTH);
  await expect(section.getByText(/Android app · added/)).toBeVisible();
  const axe = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);

  await section.getByRole("button", { name: "Remove Fixture phone from your trial" }).click();
  await expect(section.getByRole("status")).toHaveText("It can't rejoin the trial by itself.");
  await section.getByRole("button", { name: "Cancel" }).click(); // nothing happens without the second step
  await expect(section.getByText("Fixture phone")).toBeVisible();
  await section.getByRole("button", { name: "Remove Fixture phone from your trial" }).click();
  await section.getByRole("button", { name: "Yes, remove" }).click();
  await expect(page.getByRole("region", { name: "Devices on your free trial" })).toHaveCount(0, AUTH);
});
