import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-live",
  outputDir: "artifacts/playwright-live",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "artifacts/playwright-live-report", open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: process.env.PLAYWRIGHT_REUSE_APP === "true" ? undefined : {
    command: "npm run dev -- --mode e2e --host 127.0.0.1 --port 4174",
    env: { ...process.env, VITE_USE_MOCK_DELIVERY_DATA: "false" },
    url: "http://127.0.0.1:4174",
    timeout: 120_000,
    reuseExistingServer: false,
  },
  projects: [
    { name: "live-1440", use: { browserName: "chromium", viewport: { width: 1440, height: 900 } } },
    { name: "live-1024", use: { browserName: "chromium", viewport: { width: 1024, height: 768 } } },
    { name: "live-768", use: { browserName: "chromium", viewport: { width: 768, height: 1024 } } },
    { name: "live-390", use: { browserName: "chromium", viewport: { width: 390, height: 844 } } },
  ],
});
