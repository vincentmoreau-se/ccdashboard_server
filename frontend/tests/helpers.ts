import { expect, Page } from "@playwright/test";

export const PASSWORD = process.env.CCSRV_DASHBOARD_PASSWORD ?? "change-me";

/** Log in via the password form and wait until we land on the flight deck. */
export async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("••••••••••").fill(PASSWORD);
  await page.getByRole("button", { name: /ENTRER/ }).click();
  // Relative URL is resolved against playwright.config baseURL.
  await expect(page).toHaveURL("/");
}
