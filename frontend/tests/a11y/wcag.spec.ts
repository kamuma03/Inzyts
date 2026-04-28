import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * Accessibility (WCAG-AA) checks on the public/authenticated React UI.
 *
 * Failures in the ``serious`` or ``critical`` impact bucket fail the
 * build; ``moderate`` and ``minor`` are reported as warnings (a future
 * pass cleans them up).
 *
 * Pages covered:
 *  - Login (unauthenticated) — biggest blast radius if broken because
 *    every user starts there.
 *
 * Authenticated-page coverage (Dashboard, Admin, Command Center) is
 * gated behind ``PLAYWRIGHT_ADMIN_PASSWORD`` so CI without creds still
 * runs the public pass.
 */

const ADMIN_USER = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin';
const ADMIN_PASS = process.env.PLAYWRIGHT_ADMIN_PASSWORD || '';

const SERIOUS = ['serious', 'critical'] as const;

async function expectNoSeriousViolations(page: any, context: string) {
    const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

    const blocking = results.violations.filter(
        (v) => SERIOUS.includes(v.impact as any),
    );

    // Pretty-print so failure messages are useful in CI logs.
    if (blocking.length > 0) {
        const summary = blocking
            .map(
                (v) =>
                    `[${v.impact}] ${v.id}: ${v.help}\n  ` +
                    v.nodes
                        .slice(0, 3)
                        .map((n) => `→ ${n.target.join(' ')}`)
                        .join('\n  '),
            )
            .join('\n\n');
        throw new Error(
            `${context}: ${blocking.length} serious/critical a11y violations:\n${summary}`,
        );
    }

    // Surface but don't fail on moderate/minor — these tend to be styling
    // nits that are easy to fix in a follow-up but not regression-worthy.
    const minor = results.violations.filter(
        (v) => !SERIOUS.includes(v.impact as any),
    );
    if (minor.length > 0) {
        // eslint-disable-next-line no-console
        console.warn(
            `${context}: ${minor.length} moderate/minor a11y warnings ` +
                `(${minor.map((v) => v.id).join(', ')})`,
        );
    }
}

test.describe('Accessibility (WCAG-AA)', () => {
    test('Login page has no serious violations', async ({ page }) => {
        await page.goto('/login');
        // Wait for the form to render before scanning.
        await expect(page.getByLabel(/username/i)).toBeVisible();
        await expectNoSeriousViolations(page, 'Login page');
    });

    test.skip(
        !ADMIN_PASS,
        'Authed pages skipped — set PLAYWRIGHT_ADMIN_PASSWORD',
    );

    test('Dashboard has no serious violations', async ({ page }) => {
        // Login programmatically.
        await page.goto('/login');
        await page.getByLabel(/username/i).fill(ADMIN_USER);
        await page.getByLabel(/password/i).fill(ADMIN_PASS);
        await page.getByRole('button', { name: /sign in|log in/i }).click();
        await expect(page).not.toHaveURL(/\/login/);

        await expectNoSeriousViolations(page, 'Dashboard (authenticated)');
    });
});
