import { Page, expect } from '@playwright/test';

/**
 * Page object for the login screen at ``/login``.
 *
 * Encapsulates the locators and "log in" workflow so the e2e specs read
 * as user actions rather than DOM traversals. If the login form is
 * restructured in the future, only this file changes.
 */
export class LoginPage {
    constructor(public readonly page: Page) {}

    async goto(): Promise<void> {
        await this.page.goto('/login');
    }

    async login(username: string, password: string): Promise<void> {
        // Match by accessible role/name where possible — that doubles as
        // a basic accessibility check (the form must have proper labels).
        await this.page.getByLabel(/username/i).fill(username);
        await this.page.getByLabel(/password/i).fill(password);
        await this.page.getByRole('button', { name: /sign in|log in/i }).click();
    }

    async expectLoggedIn(): Promise<void> {
        // After successful login the app navigates away from /login.
        await expect(this.page).not.toHaveURL(/\/login/);
    }

    async expectLoginError(): Promise<void> {
        // Failed login should keep us on /login and show some error text.
        await expect(this.page).toHaveURL(/\/login/);
        await expect(
            this.page.getByText(/invalid|incorrect|failed/i)
        ).toBeVisible();
    }
}
