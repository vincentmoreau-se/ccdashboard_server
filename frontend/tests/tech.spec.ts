import { test, expect, Page } from "@playwright/test";

const PASSWORD = process.env.CCSRV_DASHBOARD_PASSWORD ?? "change-me";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("••••••••••").fill(PASSWORD);
  await page.getByRole("button", { name: /ENTRER/ }).click();
  await expect(page).toHaveURL("http://localhost:5180/");
}

test("tech-tooling page is accessible from nav", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "TECHNOLOGIES" }).click();
  await expect(page).toHaveURL(/\/tech$/);
});

test("tech-tooling page renders title and KPI gauges", async ({ page }) => {
  await login(page);
  await page.goto("/tech");
  await expect(page.getByText("Technologies & outils")).toBeVisible();
  // KPI gauge labels
  await expect(page.getByText("Langages")).toBeVisible();
  await expect(page.getByText("Frameworks")).toBeVisible();
  await expect(page.getByText("Outils intégrés")).toBeVisible();
  await expect(page.getByText("Outils utilisateur")).toBeVisible();
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
