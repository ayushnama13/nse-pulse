import { defineConfig } from '@playwright/test'

// Smoke tests for the migrated UI. Setup (one-time):
//   npm i -D @playwright/test && npx playwright install chromium
// Run:  npx playwright test
// Assumes the FastAPI backend is running on :8000 (vite dev proxies /api & /ws).
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173/',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
