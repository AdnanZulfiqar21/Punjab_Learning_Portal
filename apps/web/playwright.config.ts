import { defineConfig, devices } from "@playwright/test";

// End-to-end journeys against a running API (real imported catalogue) and web server.
// Locally: start the API on :8100 and `pnpm build && pnpm start`, then `pnpm e2e`. CI starts both first.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  // A retry is diagnostic only: a test that needs one fails CI (it hid a real form-swap defect once).
  failOnFlakyTests: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
});
