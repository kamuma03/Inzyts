import { test, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';

/**
 * Critical user journey — exercises the React UI end-to-end against a
 * running stack (``./start_app.sh``).
 *
 * The test verifies:
 *  - login page renders without console errors
 *  - bad credentials produce a visible error
 *  - good credentials authenticate and navigate to the Dashboard
 *  - the Dashboard's primary affordances are reachable
 *
 * The intent is NOT 100% feature coverage — it's a smoke test that the
 * critical path from "user lands on the site" to "user can start an
 * analysis" works after every change. Coverage of analysis pipelines
 * lives in the backend integration tests.
 */

const ADMIN_USER = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin';
const ADMIN_PASS = process.env.PLAYWRIGHT_ADMIN_PASSWORD || '';

test.describe('Critical user journey', () => {
    test('login page renders without console errors', async ({ page }) => {
        const errors: string[] = [];
        page.on('pageerror', (e) => errors.push(e.message));
        page.on('console', (m) => {
            if (m.type() === 'error') errors.push(m.text());
        });

        const login = new LoginPage(page);
        await login.goto();

        await expect(page.getByLabel(/username/i)).toBeVisible();
        await expect(page.getByLabel(/password/i)).toBeVisible();
        await expect(
            page.getByRole('button', { name: /sign in|log in/i })
        ).toBeVisible();

        // No uncaught errors during render.
        expect(errors, `Console errors on login render: ${errors.join('\n')}`)
            .toHaveLength(0);
    });

    test('bad credentials surface a visible error', async ({ page }) => {
        const login = new LoginPage(page);
        await login.goto();
        await login.login('definitely-not-a-user', 'wrong-password');
        await login.expectLoginError();
    });

    test.skip(
        !ADMIN_PASS,
        'Skipping authed flow — set PLAYWRIGHT_ADMIN_PASSWORD to enable',
    );

    test('good credentials authenticate and land on the Dashboard', async ({ page }) => {
        const login = new LoginPage(page);
        const dash = new DashboardPage(page);

        await login.goto();
        await login.login(ADMIN_USER, ADMIN_PASS);
        await login.expectLoggedIn();

        await dash.expectVisible();

        // The session token must be in sessionStorage, not localStorage —
        // SECURITY.md requirement that's easy to regress when adding
        // "remember me" functionality.
        const storage = await page.evaluate(() => ({
            session: sessionStorage.getItem('inzyts_jwt_token'),
            local: localStorage.getItem('inzyts_jwt_token'),
        }));
        expect(storage.session, 'JWT must be in sessionStorage').toBeTruthy();
        expect(storage.local, 'JWT must NOT be in localStorage').toBeNull();
    });
});
