import { test, expect } from "@playwright/test";

const PASSWORD = process.env.CCSRV_DASHBOARD_PASSWORD ?? "change-me";

test("unauthenticated visit redirects to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("authentification requise")).toBeVisible();
});

test("wrong password shows an error", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("••••••••••").fill("wrong-code");
  await page.getByRole("button", { name: /ENTRER/ }).click();
  await expect(page.getByText(/ACCÈS REFUSÉ/)).toBeVisible();
});

test("correct password lands on the flight deck", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("••••••••••").fill(PASSWORD);
  await page.getByRole("button", { name: /ENTRER/ }).click();
  await expect(page).toHaveURL("http://localhost:5180/");
  await expect(page.getByText("Activité temps réel")).toBeVisible();
});
