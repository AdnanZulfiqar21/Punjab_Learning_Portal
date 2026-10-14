import { expect, test } from "@playwright/test";

// P18.S2.T1 (SECURITY-SUITE-01): one place for the common web risks this app handles itself.
// * CSRF: every route handler that changes something with the session cookie refuses a cross-site request (Origin must
//   match Host) and one without an Origin, before it looks at the session. Server actions rely on Next.js's own
//   Origin/Host check; the session cookie is HttpOnly and SameSite=Lax.
// * XSS: text a learner types is shown as text, never as markup, wherever it is displayed back (here, a help request
//   seen by the learner and by support staff).
// Labelled fixture accounts only.
const AUTH = { timeout: 20_000 };
const ID = "00000000-0000-4000-8000-000000000000";
const MUTATING: [string, string][] = [
  ["POST", "/account/sign-out"],
  ["POST", `/help/${ID}/screenshots`],
  ["POST", `/practice/written/${ID}/questions/1/rescan`],
  ["POST", `/practice/written/${ID}/upload`],
  ["POST", `/studio/assets/${ID}/upload`],
  ["POST", "/studio/imports/upload"],
  ["POST", `/studio/lectures/${ID}/master-upload`],
  ["POST", `/studio/sources/${ID}/original`],
  ["PUT", `/studio/uploads/${ID}`],
];
const PAYLOAD = `<img src="x" onerror="window.__xss=1"><script>window.__xss=2</script> Fixture ${Date.now()}`;

test.skip(({ isMobile }) => isMobile, "Request-level checks run once, on desktop");

test("route handlers refuse cross-site and origin-less requests", async ({ request, baseURL }) => {
  for (const [method, path] of MUTATING) {
    for (const origin of ["https://attacker.example", null]) {
      const res = await request.fetch(path, {
        method,
        headers: { "Content-Type": "application/octet-stream", ...(origin ? { Origin: origin } : {}) },
        data: Buffer.from("fixture"),
        maxRedirects: 0,
      });
      expect(res.status(), `${method} ${path} from ${origin ?? "no origin"}`).toBe(403);
    }
  }
  // The same request from the app's own origin gets past the origin check (and then needs a session).
  const own = await request.fetch(`/practice/written/${ID}/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream", Origin: new URL(baseURL!).origin },
    data: Buffer.from("fixture"),
  });
  expect(own.status()).toBe(401);
});

test("the session cookie is HttpOnly and SameSite, and typed text is never markup", async ({ page, browser }) => {
  test.slow();
  await page.goto("/signin?next=/help");
  await page.getByRole("button", { name: "New here? Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-security-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("security-fixture-pass-1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/:\d+\/help/, AUTH);
  const cookie = (await page.context().cookies()).find((c) => c.name === "portal_session");
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");

  await page.getByRole("link", { name: "New request" }).click();
  await page.getByLabel("What is it about?").selectOption("account");
  await page.getByLabel("Summary").fill(`Fixture markup check ${Date.now()}`);
  await page.getByLabel("Details").fill(PAYLOAD);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page).toHaveURL(/:\d+\/help\/[0-9a-f-]{36}$/, AUTH);
  await expect(page.getByText(PAYLOAD)).toBeVisible(AUTH); // shown as the learner typed it
  expect(await page.locator('main img[src="x"]').count()).toBe(0);
  expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();

  const agent = await (await browser.newContext()).newPage();
  await agent.goto(`/signin?next=${encodeURIComponent(new URL(page.url()).pathname.replace("/help/", "/studio/support/"))}`);
  await agent.getByLabel("Email").fill("studio-support@example.com");
  await agent.getByLabel("Password").fill("studio-fixture-pass-1"); // pragma: allowlist secret (dev-seed fixture)
  await agent.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(agent.getByText(PAYLOAD)).toBeVisible(AUTH); // staff see it as text too
  expect(await agent.locator('main img[src="x"]').count()).toBe(0);
  expect(await agent.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
});
