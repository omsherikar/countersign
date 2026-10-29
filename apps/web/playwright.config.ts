import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests for the 60-second pitch path (ARCHITECTURE section 12,
 * D33, D49). They drive the running compose stack from the host and share
 * one seeded database, so they run one at a time in file order. Only
 * Playwright's bundled headless Chromium is used; no `channel` is ever set,
 * so no installed browser is launched or copied. A student's sign-in goes
 * through the Demo DigiLocker and back, so a test may take a few minutes on
 * a busy machine.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 240_000,
  expect: { timeout: 30_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    browserName: "chromium",
    headless: true,
    viewport: { width: 1440, height: 900 },
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    { name: "sign-in", testMatch: /auth\.setup\.ts$/ },
    { name: "demo-path", testMatch: /\.spec\.ts$/, dependencies: ["sign-in"] },
  ],
});
