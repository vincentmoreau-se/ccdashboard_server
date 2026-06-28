import { test, expect } from "@playwright/test";
import { login } from "./helpers";

test("tech-tooling page is accessible from nav", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "TECHNOLOGIES" }).click();
  await expect(page).toHaveURL(/\/tech$/);
});

test("tech-tooling page renders title and KPI gauges", async ({ page }) => {
  await login(page);
  await page.goto("/tech");
  await expect(page.getByText("Technologies & outils")).toBeVisible();
  // All six KPI gauge labels (use .first() — some labels are reused as panel titles).
  await expect(page.getByText("Langages").first()).toBeVisible();
  await expect(page.getByText("Frameworks").first()).toBeVisible();
  await expect(page.getByText("Outils intégrés").first()).toBeVisible();
  await expect(page.getByText("Outils utilisateur").first()).toBeVisible();
  await expect(page.getByText("Skills").first()).toBeVisible();
  await expect(page.getByText("Serveurs MCP").first()).toBeVisible();
});

test("tech-tooling page renders chart panels with recharts SVGs or empty state", async ({
  page,
}) => {
  await login(page);
  await page.goto("/tech");
  // Panel titles must always be present
  await expect(page.getByText("Langages — mix")).toBeVisible();
  await expect(page.getByText("Frameworks — top 10")).toBeVisible();
  await expect(page.getByText("Outils intégrés — top 10")).toBeVisible();
  await expect(page.getByText("Outils utilisateur — top 10")).toBeVisible();
  // Either recharts SVGs or "Aucune donnée" placeholders are present
  const charts = page.locator("svg.recharts-surface");
  const empties = page.getByText("Aucune donnée");
  const chartCount = await charts.count();
  const emptyCount = await empties.count();
  expect(chartCount + emptyCount).toBeGreaterThan(0);
});
