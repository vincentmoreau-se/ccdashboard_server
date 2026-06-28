import { defineConfig, devices } from "@playwright/test";

// Assumes the backend (:8000, seeded) and Vite dev server (:5173) are already
// running. Run `npm run dev` + the uvicorn server, then `npm run test:e2e`.
export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  expect: { timeout: 8000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:5180",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
});
