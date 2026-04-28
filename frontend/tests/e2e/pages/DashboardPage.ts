import { Page, expect } from '@playwright/test';

/**
 * Page object for the post-login Dashboard / Command Center landing page.
 *
 * Verifies the user successfully landed on the authenticated UI and
 * exposes shortcuts to the most common navigation actions.
 */
export class DashboardPage {
    constructor(public readonly page: Page) {}

    async expectVisible(): Promise<void> {
        // The Command Center is the main landing UI — assert at least one
        // of its top-level affordances is present. We intentionally assert
        // on multiple alternatives so a UI rename of one element doesn't
        // break the whole e2e flow.
        await expect(
            this.page.locator('header').or(
                this.page.getByRole('banner')
            )
        ).toBeVisible({ timeout: 15_000 });
    }

    async openAnalysisForm(): Promise<void> {
        // Look for any link/button that takes us to "new analysis" UI.
        await this.page
            .getByRole('button', { name: /new analysis|start analysis|analyze/i })
            .first()
            .click({ timeout: 10_000 })
            .catch(async () => {
                // Fall back to a link if no matching button exists.
                await this.page
                    .getByRole('link', { name: /new analysis|analyze/i })
                    .first()
                    .click();
            });
    }
}
