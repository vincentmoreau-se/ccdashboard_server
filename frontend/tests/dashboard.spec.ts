import { test, expect } from "@playwright/test";
import { login } from "./helpers";

test("war-room renders KPI gauges with live data", async ({ page }) => {
  await login(page);
  await expect(page.getByText("Sessions actives")).toBeVisible();
  await expect(page.getByText("Débit tokens")).toBeVisible();
  // top-teams panel shows a seeded team
  await expect(page.getByText("Top équipes — maintenant")).toBeVisible();
});

test("leaderboard lists teams and can toggle to participants", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "CLASSEMENT" }).click();
  await expect(page).toHaveURL(/\/leaderboard$/);
  await expect(page.getByRole("link", { name: "team-rocket" })).toBeVisible();
  await page.getByRole("button", { name: "Participants" }).click();
  await expect(page.getByText("Alice")).toBeVisible();
});

test("history page renders charts", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "HISTORIQUE" }).click();
  await expect(page).toHaveURL(/\/history$/);
  await expect(page.getByText("Coût total")).toBeVisible();
  await expect(page.getByText("Répartition par modèle")).toBeVisible();
  // recharts renders inline SVGs
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
});

test("team drilldown shows sessions", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "CLASSEMENT" }).click();
  await page.getByRole("link", { name: "team-rocket" }).click();
  await expect(page).toHaveURL(/\/teams\/team-rocket$/);
  await expect(page.getByText("Membres")).toBeVisible();
  await expect(page.getByText("rocket-launcher").first()).toBeVisible();
});
