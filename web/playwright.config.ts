import { defineConfig } from "@playwright/test";

/**
 * End-to-end run against the real API (local PostgreSQL, in-memory storage) and the Vite
 * dev server. Uses the installed Chrome, so no browser download is needed.
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://localhost:5180",
    channel: process.env.CI ? undefined : "chrome",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "python -m uv run uvicorn clinical_ledger.main:app --port 8000",
      cwd: "..",
      url: "http://localhost:8000/api/v1/health",
      env: { S3_BACKEND: "memory" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 5180 --strictPort",
      url: "http://localhost:5180",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
