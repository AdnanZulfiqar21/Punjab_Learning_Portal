import { defineConfig, devices } from "@playwright/test";

// End-to-end journeys against a running API (real imported catalogue) and web server.
// Locally: start the API on :8100 and `pnpm build && pnpm start`, then `pnpm e2e`. CI starts both first.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  // The suite drives one local API process; auth journeys run deliberate argon2 hashes. Bounded parallelism keeps
  // results about the product, not about saturating a laptop or CI runner.
  workers: process.env.CI ? 2 : 3,
  // A retry is diagnostic only: a test that needs one fails CI (it hid a real form-swap defect once).
  failOnFlakyTests: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", testIgnore: /service-overview\.spec\.ts/, use: { ...devices["Desktop Chrome"] } },
    { name: "phone", testIgnore: /service-overview\.spec\.ts/, use: { ...devices["Pixel 7"] } },
    // P19.S2.T1 (BROWSERS-01): the cross-browser journeys in the other supported engines.
    { name: "firefox", testMatch: /browsers\.spec\.ts/, use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", testMatch: /browsers\.spec\.ts/, use: { ...devices["Desktop Safari"] } },
    { name: "iphone", testMatch: /browsers\.spec\.ts/, use: { ...devices["iPhone 13"] } },
    // STAFFING-01 closes Class XI Biology marking while it checks the learner notice. Written starts in the other
    // projects read that same capacity, so this file runs only after they have finished.
    {
      name: "staffing",
      testMatch: /service-overview\.spec\.ts/,
      dependencies: ["desktop", "phone", "firefox", "webkit", "iphone"],
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
