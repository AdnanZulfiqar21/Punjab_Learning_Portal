import { expect, type Page } from "@playwright/test";

// AUTH-PASSWORD-01: sign-up emails a 6-digit code. In development/test the API keeps it in its local outbox (nothing is
// sent), and the development-only `last-code` route lets a test read it, so the real verification step still runs.
const API = process.env.PORTAL_API_INTERNAL_ORIGIN ?? "http://127.0.0.1:8100";
const SLOW = { timeout: 20_000 };

/** Technical fixture values for the required sign-up fields (not real personal data). */
export const SIGNUP_PHONE = "0300 0000000";
export const SIGNUP_DOB = "2008-01-01";
export const SIGNUP_FIRST_NAME = "Test";
export const SIGNUP_SURNAME = "Learner";

/** Fill the sign-up fields that the sign-in form doesn't have (call after switching to "Create account"). */
export async function fillSignupExtras(page: Page): Promise<void> {
  await page.getByLabel("First name").fill(SIGNUP_FIRST_NAME);
  await page.getByLabel("Surname").fill(SIGNUP_SURNAME);
  await page.getByLabel("Mobile number").fill(SIGNUP_PHONE);
  await page.getByLabel("Date of birth").fill(SIGNUP_DOB);
}

/** After "Create account": read the emailed code from the development outbox and confirm it. */
export async function enterEmailCode(page: Page): Promise<void> {
  await expect(page).toHaveURL(/\/signin\/verify/, SLOW);
  const email = (await page.getByTestId("pending-email").textContent())?.trim() ?? "";
  let code: string | null = null;
  for (let i = 0; i < 20 && !code; i++) {
    const res = await page.request.post(`${API}/v1/dev-auth/last-code`, { data: { email } });
    code = res.ok() ? ((await res.json()) as { code: string | null }).code : null;
    if (!code) await page.waitForTimeout(250);
  }
  expect(code, `no code in the development outbox for ${email}`).toBeTruthy();
  await page.getByLabel("6-digit code").fill(code!);
  await page.getByRole("button", { name: "Confirm email" }).click();
}
