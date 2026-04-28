import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Inzyts e2e + accessibility tests.
 *
 * Tests assume the dev stack is already running:
 *
 *   ./start_app.sh    # backend on :8000, frontend on :5173
 *
 * Run with:
 *
 *   npx playwright test            # all suites
 *   npx playwright test --headed   # with browser visible
 *   npx playwright test e2e/       # just e2e
 *   npx playwright test a11y/      # just accessibility (axe-core)
 */
export default defineConfig({
    testDir: './tests',
    timeout: 60_000,
    expect: { timeout: 10_000 },

    // Use serial workers — accessibility scans + e2e flows can interfere
    // when run in parallel against a single backend instance.
    fullyParallel: false,
    workers: 1,

    reporter: [
        ['list'],
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ],

    use: {
        baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    // The dev server is started manually (./start_app.sh) — Playwright won't
    // try to manage it. CI can override with PLAYWRIGHT_BASE_URL.
});
